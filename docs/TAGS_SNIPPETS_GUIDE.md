# 🏷️ Tags & Snippets - User Guide

## Overview
Version 2.0.41 introduces **Tags** for organizing prompts and **Snippets** for quick reusable prompt pieces.

---

## 🏷️ Tags Feature

### What are Tags?
Tags help you categorize and filter your prompt history. Think of them as labels that make it easy to find related prompts.

### Default Tags
- **code** (Blue) - Programming, code review, debugging
- **writing** (Green) - Articles, documentation, content
- **analysis** (Orange) - Data analysis, research
- **debug** (Red) - Troubleshooting, error fixing
- **review** (Purple) - Code reviews, feedback
- **tutorial** (Pink) - Learning, teaching, guides
- **test** (Cyan) - Testing, QA, validation
- **docs** (Lime) - Documentation, README files

### Adding Tags to Prompts

#### Method 1: Context Menu
1. Right-click on any prompt in history
2. Select **"🏷️ Manage Tags"**
3. Check/uncheck tags you want
4. Click **"💾 Save"**

#### Method 2: After Generation
Tags are automatically suggested based on your prompt content (coming soon).

### Filtering by Tags

#### Single Tag Filter
1. Click any tag button in the sidebar
2. Only prompts with that tag will show
3. Click again to deselect

#### Multiple Tags Filter
1. Click multiple tag buttons
2. Prompts with **any** of the selected tags will show
3. Click **"All"** button to clear filters

#### Combined Search + Tags
- Use search box **+** tag filters together
- Prompts must match both search term AND selected tags

### Tag Colors
Each tag has a unique color for quick visual identification:
- Tags appear next to prompt previews: `[code] [review]`
- Active filter buttons are highlighted in their tag color
- Inactive buttons are gray

---

## ✂️ Snippets Feature

### What are Snippets?
Snippets are reusable prompt templates or common prompt fragments that you can quickly insert into your prompts.

### Default Snippets
1. **Code Review Template**
   ```
   Review this code for:
   - Best practices
   - Performance issues
   - Security vulnerabilities
   - Code quality
   ```

2. **Bug Report**
   ```
   **Bug Description:**
   
   **Steps to Reproduce:**
   1. 
   2. 
   3. 
   
   **Expected Behavior:**
   
   **Actual Behavior:**
   ```

3. **Explain Code**
   ```
   Explain this code in simple terms:
   - What it does
   - How it works
   - Key concepts used
   ```

### Using Snippets

#### Insert Snippet
1. **Double-click** snippet in the list
2. OR press **Enter** on selected snippet
3. OR right-click → **"✂️ Insert"**
4. Snippet is inserted at cursor position in prompt area

### Creating Custom Snippets

1. Click the **"+"** button next to "✂️ Snippets"
2. Enter snippet details:
   - **Name**: Short descriptive name
   - **Category**: code, writing, debug, review, tutorial, test, docs, general
   - **Content**: The actual snippet text
3. Click **"💾 Save"**

### Managing Snippets

#### Edit Snippet
1. Right-click snippet
2. Select **"✏️ Edit"**
3. Modify name, category, or content
4. Click **"💾 Save"**

#### Delete Snippet
1. Right-click snippet
2. Select **"🗑️ Delete"**
3. Confirm deletion

### Snippet Categories
Organize snippets by category:
- **code**: Programming templates
- **writing**: Content structures
- **debug**: Troubleshooting formats
- **review**: Review checklists
- **tutorial**: Teaching templates
- **test**: Testing scenarios
- **docs**: Documentation formats
- **general**: Miscellaneous

---

## 💡 Usage Tips

### Tags Best Practices
1. **Be Consistent**: Use the same tags for similar prompts
2. **Don't Over-Tag**: 2-3 tags per prompt is usually enough
3. **Use Filters**: Regularly use tag filters to find what you need
4. **Favorite + Tags**: Combine favorites with tags for power organization

### Snippets Best Practices
1. **Keep Snippets Focused**: One purpose per snippet
2. **Use Placeholders**: Add `[INSERT HERE]` markers in your snippets
3. **Build a Library**: Create snippets for your common workflows
4. **Update Regularly**: Edit snippets as your needs evolve

### Workflow Examples

#### Example 1: Code Review Workflow
1. Tag Filter: Select **"code"** + **"review"**
2. Find similar past reviews
3. Insert **"Code Review Template"** snippet
4. Customize for current code
5. Generate and tag as **"code"** + **"review"**

#### Example 2: Bug Fixing Workflow
1. Insert **"Bug Report"** snippet
2. Fill in bug details
3. Generate solution
4. Tag as **"debug"** + **"code"**
5. Mark as favorite if solution works

#### Example 3: Tutorial Creation
1. Tag Filter: **"tutorial"**
2. Review past tutorial prompts
3. Insert **"Explain Code"** snippet
4. Add specific topic
5. Tag as **"tutorial"** + **"writing"**

---

## 🎨 Keyboard Shortcuts

### Sidebar
- **Ctrl+H**: Focus history search (coming soon)
- **Ctrl+T**: Open tag manager for selected item (coming soon)
- **Ctrl+Shift+S**: Show snippets panel (coming soon)

### Snippets
- **Enter**: Insert selected snippet
- **Delete**: Remove selected snippet
- **F2**: Edit selected snippet (coming soon)

### Tags
- **1-8**: Quick select tags 1-8 (coming soon)
- **Ctrl+0**: Clear all tag filters (coming soon)

---

## 📊 Data Storage

### Tags
Location: `~/.promptc_tags.json`

Format:
```json
[
  {
    "name": "code",
    "color": "#3b82f6"
  },
  {
    "name": "writing",
    "color": "#10b981"
  }
]
```

### Snippets
Location: `~/.promptc_snippets.json`

Format:
```json
[
  {
    "name": "Code Review Template",
    "content": "Review this code for:\\n...",
    "category": "code"
  }
]
```

### History with Tags
Location: `~/.promptc_history.json`

Format:
```json
[
  {
    "timestamp": "2025-11-06T10:30:00",
    "preview": "Create a function that...",
    "full_text": "Full prompt text here...",
    "is_favorite": false,
    "tags": ["code", "tutorial"]
  }
]
```

---

## 🔧 Troubleshooting

### Tags Not Showing
- Check if `~/.promptc_tags.json` exists
- Try clicking "🔄 Refresh" button
- Restart the application

### Snippets Not Inserting
- Ensure prompt text area is focused
- Check if snippet content is not empty
- Try right-click → Insert instead

### Tag Filter Not Working
- Clear search box to see all tagged items
- Click "All" button to reset filters
- Ensure items have tags assigned

### Lost Tags/Snippets
- Check backup files in `~/.promptc/` directory
- Tags and snippets are stored separately from history
- You can manually edit JSON files to restore data

---

## 🚀 Advanced Features (Coming Soon)

### Smart Tagging
- Auto-suggest tags based on prompt content
- Machine learning tag recommendations
- Bulk tag operations

### Snippet Variables
- Placeholders with prompt: `{{placeholder_name}}`
- Template variable substitution
- Dynamic snippet generation

### Tag Analytics
- Most used tags
- Tag combinations insights
- Tag-based statistics

### Snippet Sharing
- Export/import snippet libraries
- Community snippet marketplace
- Team snippet sync

---

## Version History

### v2.0.41 (November 6, 2025)
- ✅ Tags system with 8 default tags
- ✅ Tag filtering (single and multiple)
- ✅ Tag management UI
- ✅ Snippets library with 3 default templates
- ✅ Snippet CRUD operations
- ✅ Quick snippet insertion
- ✅ Category-based snippet organization
- ✅ Context menus for tags and snippets
- ✅ Visual tag indicators in history
- ✅ Tag + search combined filtering

---

**Need Help?** Open an issue on GitHub or check the main README.md
