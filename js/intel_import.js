/* ═══════════════════════════════════════════════════════════════
   Intel Report Import — Parse structured intelligence reports
   and plot entities, connections, and flight arcs on the map.
   ═══════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  // ── Airport IATA→coords cache (loaded once) ──
  let _airportIndex = null;

  // ── Source badge colours ──
  const SOURCE_COLOURS = {
    "primary source": "#6366f1",
    "experian":       "#2563eb",
    "pnc":            "#ef4444",
    "pnd":            "#dc2626",
    "nbtc":           "#0891b2",
    "elmer":          "#d97706",
    "daml":           "#d97706",
    "sar":            "#f59e0b",
    "gb connexus":    "#7c3aed",
    "osint":          "#22c55e",
    "companies house":"#6366f1",
    "land registry":  "#059669"
  };

  // ── Grading decoders ──
  const GRADE_SOURCE = { "1":"Known to be reliable", "2":"Usually reliable", "3":"Not usually reliable", "4":"Unreliable", "5":"Untested source" };
  const GRADE_INTEL  = { "A":"Known directly", "B":"Known indirectly", "C":"Not known personally", "D":"Not known", "E":"Suspected to be true" };
  const GRADE_HANDLE = { "P":"May be disseminated", "C":"Disseminate with conditions" };

  // Known tags that look like IATA codes but aren't airports
  const KNOWN_NON_IATA = new Set(["NFD","DOB","VRM","PPT","PNC","PND","SAR","NCA"]);

  // ═══════════════════════════════════════════════════════════════
  // Detection
  // ═══════════════════════════════════════════════════════════════
  function detectIntelReport(text) {
    if (!text || typeof text !== "string") return false;
    const lines = text.trim().split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 3) return false;
    return /^IR\d+/i.test(lines[0].trim()) && /^OP\s+/i.test(lines[1].trim());
  }

  // ═══════════════════════════════════════════════════════════════
  // Parsing
  // ═══════════════════════════════════════════════════════════════
  function parseIntelReport(text) {
    const lines = text.trim().split(/\r?\n/);
    const nonEmpty = lines.filter(l => l.trim());

    const irNumber = (nonEmpty[0] || "").trim();
    const opName   = (nonEmpty[1] || "").trim();
    const dateStr  = (nonEmpty[2] || "").trim();

    const bodyText = lines.slice(3).join("\n").trim();

    // Split on numbered entry boundaries
    const entryBlocks = [];
    let current = null;
    for (const line of bodyText.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const m = trimmed.match(/^(\d+)\.\s+(.*)/);
      if (m) {
        if (current) entryBlocks.push(current);
        current = { index: parseInt(m[1]), text: m[2] };
      } else if (current) {
        current.text += " " + trimmed;
      } else {
        entryBlocks.push({ index: 0, text: trimmed });
      }
    }
    if (current) entryBlocks.push(current);

    // Extract provenance
    let provenance = "";
    const provIdx = entryBlocks.findIndex(e => /^Provenance\s*[-–—:]/i.test(e.text));
    if (provIdx >= 0) {
      const pm = entryBlocks[provIdx].text.match(/^Provenance\s*[-–—:]\s*(.+)/i);
      provenance = pm ? pm[1].trim() : entryBlocks[provIdx].text;
      entryBlocks.splice(provIdx, 1);
    }

    const entries = entryBlocks.filter(e => e.index > 0).map(block => parseEntry(block));

    return { header: { irNumber, opName, date: dateStr }, entries, provenance };
  }

  function parseEntry(block) {
    const text = block.text;

    // ── Persons (Firstname SURNAME) ──
    const persons = [];
    const seenNames = new Set();
    const nameRe = /\b([A-Z][a-z]+)\s+([A-Z]{2,})\b/g;
    let nm;
    while ((nm = nameRe.exec(text)) !== null) {
      // Skip false positives like "Over Drive", "Fort Worth"
      if (["Over","Fort","Great","South","North","East","West","New"].includes(nm[1])) continue;
      const full = `${nm[1]} ${nm[2]}`;
      if (seenNames.has(full)) continue;
      seenNames.add(full);
      const dobRe = new RegExp(nm[2] + "[\\s\\S]*?DOB\\s+(\\d{2}\\/\\d{2}\\/\\d{4})", "i");
      const dobM = text.match(dobRe);
      persons.push({ firstName: nm[1], surname: nm[2], fullName: full, dob: dobM ? dobM[1] : null });
    }

    // ── Addresses — walk backwards from postcode to "at" keyword ──
    const addresses = [];
    const seenPC = new Set();
    const pcRe = /\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b/gi;
    let pcm;
    while ((pcm = pcRe.exec(text)) !== null) {
      const pc = pcm[1].toUpperCase().replace(/\s+/g, "");
      if (seenPC.has(pc)) continue;
      seenPC.add(pc);

      // Extract full address: find "at" or "to" then capture everything up to the postcode
      const before = text.substring(0, pcm.index);
      const atIdx = Math.max(before.lastIndexOf(" at "), before.lastIndexOf(" to a "), before.lastIndexOf(" to an "));
      let fullAddr;
      if (atIdx >= 0) {
        // Grab from after "at " to end of postcode match
        const afterAt = before.substring(atIdx).replace(/^\s*(at|to an?)\s+/i, "").trim();
        fullAddr = (afterAt + " " + pcm[1]).replace(/,\s*,/g, ",").replace(/\s+/g, " ").trim();
      } else {
        fullAddr = pcm[1]; // Just postcode
      }
      fullAddr = fullAddr.replace(/^[,\s]+/, "").replace(/[,\s]+$/, "");

      let context = "other";
      if (/lives?\s+at|resid/i.test(before)) context = "home";
      if (/offence|burgl|robbery|theft|assault|crime/i.test(before)) context = "offence";

      addresses.push({ full: fullAddr, postcode: pcm[1], normalised: pc, context });
    }

    // ── Phones ──
    const phones = [];
    const phRe = /\b(07\d{3}\s?\d{6})\b/g;
    let phm;
    while ((phm = phRe.exec(text)) !== null) {
      phones.push(phm[1].replace(/\s/g, ""));
    }

    // ── Vehicles ──
    const vehicles = [];
    const vrmRe = /VRM\s+([A-Z]{2}\d{2}\s?[A-Z]{3})/gi;
    let vm;
    while ((vm = vrmRe.exec(text)) !== null) {
      const since = text.match(/since\s+(\d{4})/i);
      vehicles.push({ vrm: vm[1].replace(/\s/g, ""), since: since ? since[1] : null });
    }

    // ── PNC IDs ──
    const pncIds = [];
    const pncRe = /PNCID\s*(\w+)/gi;
    let pnm;
    while ((pnm = pncRe.exec(text)) !== null) pncIds.push(pnm[1]);

    // ── Flights ──
    const flights = [];
    const fCodeRe = /flight\s+(?:code\s+)?([A-Z]{2,3}\d{1,4})/gi;
    const fcm = fCodeRe.exec(text);
    if (fcm) {
      const iatas = [];
      const iataRe = /\(([A-Z]{3})\)/g;
      let im;
      while ((im = iataRe.exec(text)) !== null) {
        if (!KNOWN_NON_IATA.has(im[1])) iatas.push(im[1]);
      }
      const fdm = text.match(/[Oo]n\s+(\d{2}\/\d{2}\/\d{4})/);
      flights.push({
        code: fcm[1],
        origin: iatas[0] || null,
        destination: iatas[1] || null,
        date: fdm ? fdm[1] : null
      });
    }

    // ── Passports ──
    const passports = [];
    const pptM = text.match(/PPT\s+(\d+)/i);
    if (pptM) {
      const natM = text.match(/PPT\s+\d+\s+([\w\s]+?)(?:,|which|\.|$)/i);
      const expM = text.match(/expires?\s+(?:on\s+)?(\d{2}\/\d{2}\/\d{4})/i);
      passports.push({
        number: pptM[1],
        nationality: natM ? natM[1].trim() : null,
        expiry: expM ? expM[1] : null
      });
    }

    // ── Intel grading ──
    let grading = null;
    const gm = text.match(/\((\d)([A-C])([A-C]?)\)/);
    if (gm) grading = { source: gm[1], intel: gm[2], handling: gm[3] || null };

    // ── Source tag ──
    let source = null;
    const srcRe = /\((Primary Source|Experian|PNC|PND|NBTC|ELMER|DAML|SAR|GB Connexus|OSINT|Companies House|Land Registry)\)/gi;
    const sm = srcRe.exec(text);
    if (sm) source = sm[1];

    // ── Offence type ──
    let offenceType = null;
    const offM = text.match(/offences?\s+to\s+(?:an?\s+)?(\w[\w\s]*?)(?:\s+at\b)/i);
    if (offM) offenceType = offM[1].trim();

    return {
      index: block.index, text, source, grading,
      persons, addresses, phones, vehicles, pncIds, flights, passports, offenceType
    };
  }

  // ═══════════════════════════════════════════════════════════════
  // Airport Lookup
  // ═══════════════════════════════════════════════════════════════
  async function loadAirportIndex() {
    if (_airportIndex) return _airportIndex;
    try {
      const resp = await fetch("data/airports.geojson");
      const gj = await resp.json();
      _airportIndex = {};
      for (const f of (gj.features || [])) {
        const props = f.properties || {};
        const iata = props.iata_code || props.iata || props.IATA;
        if (iata && f.geometry?.coordinates) {
          _airportIndex[iata.toUpperCase()] = {
            lat: f.geometry.coordinates[1],
            lng: f.geometry.coordinates[0],
            name: titleCase(props.name || props.NAME || iata)
          };
        }
      }
      return _airportIndex;
    } catch (e) {
      console.warn("[IntelImport] Could not load airports.geojson:", e);
      _airportIndex = {};
      return _airportIndex;
    }
  }

  // ═══════════════════════════════════════════════════════════════
  // Helpers
  // ═══════════════════════════════════════════════════════════════
  function titleCase(str) {
    return String(str).toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
  }

  function makeIcon(category, iconId, displayName) {
    const cats = window.ICON_CATEGORIES || {};
    const cat = cats[category];
    if (!cat) return { name: displayName, icon: "", category, categoryName: displayName };
    const found = cat.icons?.find(i => i.id === iconId);
    return {
      name: displayName,
      icon: found?.icon || cat.defaultIcon || "",
      category,
      categoryName: cat.name || category
    };
  }

  function gradingBadgeHtml(grading) {
    if (!grading) return "";
    const code = `${grading.source}${grading.intel}${grading.handling || ""}`;
    return `<span style="display:inline-block;background:#374151;color:#f9fafb;padding:1px 6px;border-radius:3px;font-weight:700;font-size:11px;font-family:monospace;letter-spacing:0.5px">${code}</span>`;
  }

  function sourceBadgeHtml(source) {
    if (!source) return "";
    const colour = SOURCE_COLOURS[source.toLowerCase()] || "#64748b";
    return `<span style="display:inline-block;background:${colour};color:#fff;padding:1px 7px;border-radius:3px;font-size:10px;font-weight:600;letter-spacing:0.3px">${escapeHtml(source)}</span>`;
  }

  /** Build rich hover tooltip HTML for connections */
  function buildConnectionHover(entry, parsed) {
    const parts = [];
    if (entry.source || entry.grading) {
      const badges = [sourceBadgeHtml(entry.source), gradingBadgeHtml(entry.grading)].filter(Boolean);
      parts.push(badges.join(" "));
    }
    parts.push(`<div style="max-width:320px;font-size:11px;color:#cbd5e1;line-height:1.4;margin-top:4px">${escapeHtml(truncate(entry.text, 180))}</div>`);
    parts.push(`<div style="font-size:10px;color:#64748b;margin-top:3px">${escapeHtml(parsed.header.irNumber)} ${escapeHtml(parsed.header.opName)}</div>`);
    return parts.join("");
  }

  function truncate(str, len) {
    return str.length > len ? str.substring(0, len) + "..." : str;
  }

  // ═══════════════════════════════════════════════════════════════
  // Plotting
  // ═══════════════════════════════════════════════════════════════
  async function plotIntelReport(parsed) {
    const stats = {
      persons: 0, addresses: 0, vehicles: 0, flights: 0,
      connections: 0, airports: 0, phones: 0, entries: parsed.entries.length,
      irNumber: parsed.header.irNumber, opName: parsed.header.opName
    };

    // Collect all unique data across entries
    const allPersons = new Map();
    const allAddresses = new Map();
    const allVehicles = new Map();
    const allFlights = [];
    const allPhones = new Set();
    const allPncIds = new Set();
    const allPassports = [];

    // Track which entry mentions which address (for connection hover detail)
    const addrEntryMap = new Map();  // normalisedPC → entry
    const vehEntryMap  = new Map();  // vrm → entry
    const flightEntryMap = new Map(); // flightCode → entry

    for (const entry of parsed.entries) {
      for (const p of entry.persons) {
        if (!allPersons.has(p.fullName)) allPersons.set(p.fullName, { ...p, sources: [] });
        allPersons.get(p.fullName).sources.push(entry.source);
        if (p.dob && !allPersons.get(p.fullName).dob) allPersons.get(p.fullName).dob = p.dob;
      }
      for (const a of entry.addresses) {
        if (!allAddresses.has(a.normalised)) allAddresses.set(a.normalised, a);
        if (!addrEntryMap.has(a.normalised)) addrEntryMap.set(a.normalised, entry);
      }
      for (const v of entry.vehicles) {
        if (!allVehicles.has(v.vrm)) allVehicles.set(v.vrm, v);
        if (!vehEntryMap.has(v.vrm)) vehEntryMap.set(v.vrm, entry);
      }
      for (const f of entry.flights) {
        allFlights.push(f);
        if (!flightEntryMap.has(f.code)) flightEntryMap.set(f.code, entry);
      }
      for (const ph of entry.phones) allPhones.add(ph);
      for (const pnc of entry.pncIds) allPncIds.add(pnc);
      for (const pp of entry.passports) allPassports.push(pp);
    }

    stats.phones = allPhones.size;

    // ── Step 1: Load airports ──
    const airports = await loadAirportIndex();

    // ── Step 2: Geocode all postcodes ──
    if (typeof setStatus === "function") setStatus("Geocoding addresses...");
    const geocoded = {};
    const postcodes = [...allAddresses.keys()];
    for (let i = 0; i < postcodes.length; i += 3) {
      const batch = postcodes.slice(i, i + 3);
      const results = await Promise.all(batch.map(pc => {
        const addr = allAddresses.get(pc);
        return geocodePostcode(addr.postcode).then(c => ({ pc, coords: c }));
      }));
      for (const r of results) {
        if (r.coords) geocoded[r.pc] = r.coords;
      }
    }

    // ── Step 3: Place person entities ──
    const entityIds = {};
    const allLatLngs = [];

    for (const [name, person] of allPersons) {
      const homeAddr = [...allAddresses.values()].find(a => a.context === "home");
      const homePC = homeAddr?.normalised;
      const coords = homePC && geocoded[homePC];
      if (!coords) continue;

      const latLng = [coords.lat, coords.lng || coords.lon];
      allLatLngs.push(latLng);

      const i2Values = [
        { propertyName: "Full Name", value: person.fullName }
      ];
      if (person.dob) i2Values.push({ propertyName: "Date of Birth", value: person.dob });
      for (const ph of allPhones) i2Values.push({ propertyName: "Phone", value: ph });
      for (const pnc of allPncIds) i2Values.push({ propertyName: "PNC ID", value: pnc });
      for (const v of allVehicles.keys()) i2Values.push({ propertyName: "VRM", value: v });
      for (const pp of allPassports) {
        i2Values.push({ propertyName: "Passport", value: `${pp.number}${pp.nationality ? " (" + pp.nationality.trim() + ")" : ""}` });
        if (pp.expiry) i2Values.push({ propertyName: "Passport Expiry", value: pp.expiry });
      }
      if (parsed.provenance) i2Values.push({ propertyName: "Provenance", value: parsed.provenance });
      i2Values.push({ propertyName: "Intel Ref", value: `${parsed.header.irNumber} ${parsed.header.opName}` });

      const notes = `${parsed.header.irNumber} | ${parsed.header.opName}` +
        (parsed.provenance ? `\n${parsed.provenance}` : "");

      const eid = placeEntity(
        latLng,
        makeIcon("people", "person", person.fullName),
        person.fullName,
        homeAddr?.full || "",
        notes,
        { entityType: "Person", entityName: "Person", entityId: "ET1", values: i2Values }
      );
      if (eid) {
        entityIds[`person_${name}`] = eid;
        stats.persons++;
      }
    }

    // ── Step 4: Place address markers ──
    for (const [pc, addr] of allAddresses) {
      const coords = geocoded[pc];
      if (!coords) continue;
      const latLng = [coords.lat, coords.lng || coords.lon];
      allLatLngs.push(latLng);

      const isOffence = addr.context === "offence";
      const isHome = addr.context === "home";

      let offenceNote = "";
      if (isOffence) {
        for (const entry of parsed.entries) {
          if (entry.offenceType && entry.addresses.some(a => a.normalised === pc)) {
            offenceNote = entry.offenceType;
            break;
          }
        }
      }

      const i2Values = [{ propertyName: "Address", value: addr.full }];
      if (isOffence) {
        for (const entry of parsed.entries) {
          if (entry.addresses.some(a => a.normalised === pc)) {
            const dateMatch = entry.text.match(/in\s+(\d{4})/);
            if (dateMatch) {
              i2Values.push({ propertyName: "Offence Date", value: `01/01/${dateMatch[1]}` });
              i2Values.push({ propertyName: "Offence Type", value: offenceNote || "Unknown" });
            }
          }
        }
      }
      i2Values.push({ propertyName: "Intel Ref", value: `${parsed.header.irNumber} ${parsed.header.opName}` });

      const label = isOffence
        ? `Offence: ${offenceNote ? titleCase(offenceNote) : "Location"}`
        : isHome ? "Residential Address" : "Address";

      const iconCat = isOffence ? "military" : "buildings";
      const iconId  = isOffence ? "mil_intel" : (isHome ? "house" : "building");

      // Override displayed category for offence locations (military icon but "Crime Scene" label)
      const iconOverrides = isOffence ? { categoryName: "Crime Scene" } : {};

      const eid = placeEntity(
        latLng,
        { ...makeIcon(iconCat, iconId, label), ...iconOverrides },
        `${label} — ${addr.full}`,
        addr.full,
        isOffence ? `Offence: ${titleCase(offenceNote || "unknown")}` : "",
        { entityType: isOffence ? "Crime Scene" : "Address", entityName: "Location", entityId: "ET3", values: i2Values }
      );
      if (eid) {
        entityIds[`addr_${pc}`] = eid;
        stats.addresses++;
      }
    }

    // ── Step 5: Place vehicle markers (offset from person) ──
    for (const [vrm, veh] of allVehicles) {
      const personKey = [...allPersons.keys()][0];
      const personEid = personKey ? entityIds[`person_${personKey}`] : null;
      const personEntity = personEid ? window._mapEntities.find(e => e.id === personEid) : null;
      if (!personEntity) continue;

      const latLng = [personEntity.latLng[0] + 0.0012, personEntity.latLng[1] + 0.0012];
      allLatLngs.push(latLng);

      const eid = placeEntity(
        latLng,
        makeIcon("vehicles", "car", `Vehicle ${vrm}`),
        `Vehicle: ${vrm}`,
        "",
        veh.since ? `Registered keeper since ${veh.since}` : "",
        { entityType: "Vehicle", entityName: "Vehicle", entityId: "ET5", values: [
          { propertyName: "VRM", value: vrm },
          ...(veh.since ? [{ propertyName: "Registered Since", value: veh.since }] : []),
          { propertyName: "Intel Ref", value: `${parsed.header.irNumber} ${parsed.header.opName}` }
        ]}
      );
      if (eid) {
        entityIds[`veh_${vrm}`] = eid;
        stats.vehicles++;
      }
    }

    // ── Step 6: Place airport markers & flight arcs ──
    for (const flight of allFlights) {
      const originApt  = flight.origin  ? airports[flight.origin]  : null;
      const destApt    = flight.destination ? airports[flight.destination] : null;

      if (originApt) {
        const latLng = [originApt.lat, originApt.lng];
        allLatLngs.push(latLng);
        const i2Values = [
          { propertyName: "IATA", value: flight.origin },
          { propertyName: "Airport", value: originApt.name }
        ];
        if (flight.date) i2Values.push({ propertyName: "Flight Date", value: flight.date });
        const eid = placeEntity(
          latLng,
          makeIcon("aviation", "airport", originApt.name),
          `${originApt.name} (${flight.origin})`,
          "",
          `Departure — Flight ${flight.code}`,
          { entityType: "Airport", entityName: "Location", entityId: "ET3", values: i2Values }
        );
        if (eid) { entityIds[`apt_${flight.origin}`] = eid; stats.airports++; }
      }

      if (destApt) {
        const latLng = [destApt.lat, destApt.lng];
        allLatLngs.push(latLng);
        const i2Values = [
          { propertyName: "IATA", value: flight.destination },
          { propertyName: "Airport", value: destApt.name }
        ];
        if (flight.date) i2Values.push({ propertyName: "Flight Date", value: flight.date });
        const eid = placeEntity(
          latLng,
          makeIcon("aviation", "airport", destApt.name),
          `${destApt.name} (${flight.destination})`,
          "",
          `Arrival — Flight ${flight.code}`,
          { entityType: "Airport", entityName: "Location", entityId: "ET3", values: i2Values }
        );
        if (eid) { entityIds[`apt_${flight.destination}`] = eid; stats.airports++; }
      }

      // Flight arc (great circle)
      if (originApt && destApt) {
        const arcPoints = buildGreatCircleArc(
          [originApt.lat, originApt.lng], [destApt.lat, destApt.lng], 50
        );
        const flightEntry = flightEntryMap.get(flight.code);
        const arcLine = L.polyline(arcPoints, {
          color: "#38bdf8", weight: 2.5, opacity: 0.8, dashArray: "8, 6"
        }).addTo(window._map);
        arcLine.bindTooltip(
          `<div style="text-align:center">` +
          `<strong style="color:#38bdf8">Flight ${escapeHtml(flight.code)}</strong><br>` +
          `<span style="font-size:12px">${escapeHtml(originApt.name)} → ${escapeHtml(destApt.name)}</span>` +
          (flight.date ? `<br><span style="font-size:11px;color:#94a3b8">${escapeHtml(flight.date)}</span>` : "") +
          (flightEntry ? `<br>${sourceBadgeHtml(flightEntry.source)} ${gradingBadgeHtml(flightEntry.grading)}` : "") +
          `</div>`,
          { sticky: true, direction: "top", opacity: 0.95 }
        );

        // Formal connection for network graph
        const fromEid = entityIds[`apt_${flight.origin}`];
        const toEid   = entityIds[`apt_${flight.destination}`];
        if (fromEid && toEid) {
          const fromE = window._mapEntities.find(e => e.id === fromEid);
          const toE   = window._mapEntities.find(e => e.id === toEid);
          if (fromE && toE) {
            addConnection(fromE.latLng, toE.latLng, `Flight ${flight.code}`, "manual", {
              fromId: fromEid, toId: toEid,
              fromLabel: `${originApt.name} (${flight.origin})`,
              toLabel: `${destApt.name} (${flight.destination})`,
              hoverDetail: flightEntry ? buildConnectionHover(flightEntry, parsed) : `Flight ${flight.code}`
            });
            stats.connections++;
          }
        }
        stats.flights++;
      }
    }

    // ── Step 7: Draw connections ──
    const primaryPerson = [...allPersons.keys()][0];
    const personEid = primaryPerson ? entityIds[`person_${primaryPerson}`] : null;
    const personEntity = personEid ? window._mapEntities.find(e => e.id === personEid) : null;

    if (personEntity) {
      for (const [pc, addr] of allAddresses) {
        const addrEid = entityIds[`addr_${pc}`];
        const addrEntity = addrEid ? window._mapEntities.find(e => e.id === addrEid) : null;
        if (!addrEntity) continue;

        const entry = addrEntryMap.get(pc);
        const label = addr.context === "home" ? "Resides at"
                    : addr.context === "offence" ? "Offence location"
                    : "Associated address";

        addConnection(personEntity.latLng, addrEntity.latLng, label, "manual", {
          fromId: personEid, toId: addrEid,
          fromLabel: primaryPerson, toLabel: addr.full,
          hoverDetail: entry ? buildConnectionHover(entry, parsed) : ""
        });
        stats.connections++;
      }

      for (const [vrm] of allVehicles) {
        const vehEid = entityIds[`veh_${vrm}`];
        const vehEntity = vehEid ? window._mapEntities.find(e => e.id === vehEid) : null;
        if (!vehEntity) continue;

        const entry = vehEntryMap.get(vrm);
        addConnection(personEntity.latLng, vehEntity.latLng, `Reg. keeper: ${vrm}`, "manual", {
          fromId: personEid, toId: vehEid,
          fromLabel: primaryPerson, toLabel: vrm,
          hoverDetail: entry ? buildConnectionHover(entry, parsed) : ""
        });
        stats.connections++;
      }

      for (const flight of allFlights) {
        if (flight.destination) {
          const aptEid = entityIds[`apt_${flight.destination}`];
          const aptEntity = aptEid ? window._mapEntities.find(e => e.id === aptEid) : null;
          if (!aptEntity) continue;

          const entry = flightEntryMap.get(flight.code);
          addConnection(personEntity.latLng, aptEntity.latLng, `Travelled: ${flight.code}`, "manual", {
            fromId: personEid, toId: aptEid,
            fromLabel: primaryPerson,
            toLabel: airports[flight.destination]?.name || flight.destination,
            hoverDetail: entry ? buildConnectionHover(entry, parsed) : ""
          });
          stats.connections++;
        }
      }
    }

    // ── Step 8: Refresh UI ──
    if (typeof window.refreshNetworkGraph === "function") window.refreshNetworkGraph();
    if (typeof window.refreshTimeline === "function") window.refreshTimeline();
    if (typeof updateDashboardCounts === "function") updateDashboardCounts();
    if (window.CRDashboard?.logActivity) {
      window.CRDashboard.logActivity(
        "Intel report imported",
        `${parsed.header.irNumber} ${parsed.header.opName} — ${stats.persons} person(s), ${stats.addresses} address(es), ${stats.flights} flight(s)`,
        "entity"
      );
    }
    if (typeof setStatus === "function") setStatus(`Imported: ${parsed.header.irNumber} ${parsed.header.opName}`);

    // ── Step 9: Fit map ──
    if (allLatLngs.length > 0 && window._map) {
      window._map.fitBounds(L.latLngBounds(allLatLngs).pad(0.15));
    }

    // ── Step 10: Summary ──
    showImportSummary(stats, parsed);
    return stats;
  }

  // ═══════════════════════════════════════════════════════════════
  // Great circle arc
  // ═══════════════════════════════════════════════════════════════
  function buildGreatCircleArc(from, to, numPoints) {
    const toRad = d => d * Math.PI / 180;
    const toDeg = r => r * 180 / Math.PI;
    const lat1 = toRad(from[0]), lng1 = toRad(from[1]);
    const lat2 = toRad(to[0]),   lng2 = toRad(to[1]);
    const d = 2 * Math.asin(Math.sqrt(
      Math.pow(Math.sin((lat1 - lat2) / 2), 2) +
      Math.cos(lat1) * Math.cos(lat2) * Math.pow(Math.sin((lng1 - lng2) / 2), 2)
    ));
    if (d < 1e-10) return [from, to];
    const points = [];
    for (let i = 0; i <= numPoints; i++) {
      const f = i / numPoints;
      const A = Math.sin((1 - f) * d) / Math.sin(d);
      const B = Math.sin(f * d) / Math.sin(d);
      const x = A * Math.cos(lat1) * Math.cos(lng1) + B * Math.cos(lat2) * Math.cos(lng2);
      const y = A * Math.cos(lat1) * Math.sin(lng1) + B * Math.cos(lat2) * Math.sin(lng2);
      const z = A * Math.sin(lat1) + B * Math.sin(lat2);
      points.push([toDeg(Math.atan2(z, Math.sqrt(x * x + y * y))), toDeg(Math.atan2(y, x))]);
    }
    return points;
  }

  // ═══════════════════════════════════════════════════════════════
  // Summary Modal
  // ═══════════════════════════════════════════════════════════════
  function showImportSummary(stats, parsed) {
    document.getElementById("intel-import-modal")?.remove();

    // Build grading detail rows with decoded meanings
    const gradingRows = parsed.entries.filter(e => e.grading).map(e => {
      const g = e.grading;
      const code = `${g.source}${g.intel}${g.handling || ""}`;
      const srcMeaning = GRADE_SOURCE[g.source] || "";
      const intMeaning = GRADE_INTEL[g.intel] || "";
      const hdlMeaning = g.handling ? (GRADE_HANDLE[g.handling] || "") : "";
      return `<div class="iis-grading-row">
        <span class="iis-grading-num">${e.index}.</span>
        <span class="iis-grading-code">${code}</span>
        ${sourceBadgeHtml(e.source)}
        <span class="iis-grading-decode">${srcMeaning}${intMeaning ? " / " + intMeaning : ""}${hdlMeaning ? " / " + hdlMeaning : ""}</span>
      </div>`;
    }).join("");

    const modal = document.createElement("div");
    modal.id = "intel-import-modal";
    modal.className = "intel-import-modal";
    modal.innerHTML = `
      <div class="intel-import-modal-content">
        <div class="iis-header">
          <div class="iis-title">Intel Report Imported</div>
          <div class="iis-ref">${escapeHtml(stats.irNumber)} — ${escapeHtml(stats.opName)}</div>
          ${parsed.header.date ? `<div class="iis-date">${escapeHtml(parsed.header.date)}</div>` : ""}
        </div>
        <div class="iis-grid">
          <div class="iis-stat"><div class="iis-value">${stats.entries}</div><div class="iis-label">Intel Entries</div></div>
          <div class="iis-stat"><div class="iis-value">${stats.persons}</div><div class="iis-label">Persons</div></div>
          <div class="iis-stat"><div class="iis-value">${stats.addresses}</div><div class="iis-label">Addresses</div></div>
          <div class="iis-stat"><div class="iis-value">${stats.vehicles}</div><div class="iis-label">Vehicles</div></div>
          <div class="iis-stat"><div class="iis-value">${stats.flights}</div><div class="iis-label">Flights</div></div>
          <div class="iis-stat"><div class="iis-value">${stats.airports}</div><div class="iis-label">Airports</div></div>
          <div class="iis-stat"><div class="iis-value">${stats.connections}</div><div class="iis-label">Connections</div></div>
          <div class="iis-stat"><div class="iis-value">${stats.phones}</div><div class="iis-label">Phones</div></div>
        </div>
        ${gradingRows ? `<div class="iis-gradings"><div class="iis-gradings-title">Intel Grading</div>${gradingRows}</div>` : ""}
        ${parsed.provenance ? `<div class="iis-provenance"><strong>Provenance:</strong> ${escapeHtml(parsed.provenance)}</div>` : ""}
        <button class="iis-close-btn" type="button">OK</button>
      </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector(".iis-close-btn").addEventListener("click", () => modal.remove());
    modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });
  }

  // ═══════════════════════════════════════════════════════════════
  // Entry point
  // ═══════════════════════════════════════════════════════════════
  async function importFromText(text, filename) {
    const parsed = parseIntelReport(text);
    if (!parsed.entries.length) {
      if (typeof showToast === "function") showToast("No intel entries found in file", "error");
      return null;
    }
    console.log(`[IntelImport] Parsed ${parsed.entries.length} entries from ${filename || "text"}`);
    return plotIntelReport(parsed);
  }

  async function extractTextFromFile(file) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (ext === "pdf") {
      if (!window.pdfjsLib) throw new Error("PDF.js not loaded — cannot read PDF files");
      const buf = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
      const pages = [];
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const tc = await page.getTextContent();
        pages.push(tc.items.map(item => item.str).join(" "));
      }
      return pages.join("\n");
    }
    return await file.text();
  }

  function initQuickImport() {
    const btn = document.getElementById("quick-intel-import");
    if (!btn) return;
    btn.addEventListener("click", () => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".txt,.pdf";
      input.addEventListener("change", async () => {
        const file = input.files?.[0];
        if (!file) return;
        try {
          const text = await extractTextFromFile(file);
          if (!detectIntelReport(text)) {
            if (typeof showToast === "function") showToast("Not an intelligence report \u2014 expected IR number + OP name header", "error", 4000);
            return;
          }
          await importFromText(text, file.name);
        } catch (err) {
          console.error("[IntelImport] Import failed:", err);
          if (typeof showToast === "function") showToast(`Intel import failed: ${err.message}`, "error");
        }
      });
      input.click();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQuickImport);
  } else {
    initQuickImport();
  }

  window.IntelImport = { detectIntelReport, parseIntelReport, plotIntelReport, importFromText };
})();
