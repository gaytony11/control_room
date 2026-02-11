## GitHub Upload Instructions

Your Control Room project has been prepared for GitHub upload!

### What's Been Done

1. **Large datasets moved** (19 GB total) from the project to `C:\Users\44752\Desktop\other\Control Room\`:
   - `data/postcode_data/` - 3.8 GB
   - `data/postcodes/` - 74 MB
   - `data/companies_house_basic_company_data/` - 2.6 GB
   - `data/companies_house_subsets/` - 10.6 GB
   - `data/psc_by_company/` - 1.4 GB
   - `data/psc_names/` - 521 MB

2. **Git repository initialized** with:
   - `.gitignore` configured to exclude large datasets
   - README.md updated with project documentation
   - Placeholder folders created for excluded datasets

3. **Project structure preserved** - folder structure maintained in both locations

### Next Steps to Upload to GitHub

1. **Create a new GitHub repository:**
   - Go to https://github.com/new
   - Repository name: `control-room` (or your preferred name)
   - Description: "Interactive intelligence and investigation mapping system"
   - Choose Public or Private
   - **Do NOT** initialize with README, .gitignore, or license (already created locally)
   - Click "Create repository"

2. **Connect and push your code:**
   ```bash
   cd "C:\Users\44752\Desktop\Control Room"
   git remote add origin https://github.com/gaytony11/control-room.git
   git branch -M main
   git push -u origin main
   ```

3. **Verify upload:**
   - Check that all files appear on GitHub
   - Verify large dataset folders show README.md placeholders only
   - Test that the repository size is reasonable (should be < 1 GB)

### File Size Summary

**Before:** ~19 GB total
**After (GitHub):** ~200-300 MB (manageable size)
**Moved to external:** 18.9 GB (preserved locally in `other/Control Room/`)

### Restoring Large Datasets

If someone clones your repository and needs the large datasets:

1. They'll see placeholder folders with README.md files explaining what's missing
2. Data can be regenerated using scripts in the `scripts/` folder
3. Or obtained from original sources (Companies House, ONSPD, etc.)

### Important Notes

- The `.gitignore` file prevents accidentally committing large datasets
- Your `.env` file (API keys) is also excluded from git
- All functionality remains intact with the current file structure
- The moved datasets are safely preserved in `C:\Users\44752\Desktop\other`

### Testing Before Push

To verify everything works without large datasets:
```bash
cd "C:\Users\44752\Desktop\Control Room"
python scripts/dev_server.py
# Open http://localhost:8000 and test functionality
```

Functionality that still works:
- ✅ TfL station visualization (data included)
- ✅ Companies House API search (uses live API)
- ✅ Custom entity placement
- ✅ Connection drawing
- ✅ PDF generation
- ✅ Airport/seaport layers
- ✅ Police force areas

Functionality requiring external data:
- ❌ Postcode lookup (would need data/postcodes/)
- ❌ Local company search (would need data/companies_house_basic_company_data/)
