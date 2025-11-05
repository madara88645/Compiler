# 📜 Recent Prompts Sidebar - User Guide

## Overview
Version 2.0.40 introduces a **Recent Prompts Sidebar** that keeps track of your prompt history and favorites for quick access.

## Features

### 🔍 Search & Filter
- **Search Box**: Type to filter prompts by content
- Real-time filtering as you type
- Clear search to show all items

### 📋 History List
- Shows your 100 most recent prompts
- Each item displays a preview (first 100 characters)
- Favorites marked with ⭐ star icon
- Automatic saving after each generation

### 🎯 Quick Actions

#### Loading Prompts
- **Double-click** any item to load it into the prompt area
- Press **Enter** on selected item
- **Right-click → Load** from context menu

#### Managing Items
- **Delete**: Press **Delete** key or right-click → Delete
- **Favorite**: Right-click → Toggle Favorite
- **Clear All**: Click "🗑️ Clear All" button to remove all history

#### Sidebar Controls
- **Toggle Visibility**: Click ◀/▶ button to show/hide sidebar
- **Refresh**: Click "🔄 Refresh" to reload from disk
- **Clear All**: Remove all history items

### 💾 Data Storage
History is saved to:
```
%USERPROFILE%\.promptc_history.json
```

Format:
```json
[
  {
    "timestamp": "2025-11-05T10:30:00",
    "preview": "Create a function that...",
    "full_text": "Create a function that does X, Y, and Z...",
    "is_favorite": false
  }
]
```

### ⌨️ Keyboard Shortcuts
- **Enter**: Load selected prompt
- **Delete**: Remove selected prompt
- **Right-click**: Open context menu
- **Ctrl+F**: Focus search box (if in sidebar)

## Usage Tips

### 1. Quick Recall
Use the sidebar to quickly recall and reuse previous prompts without retyping.

### 2. Favorite Important Prompts
Mark frequently used prompts as favorites (⭐) for easy identification.

### 3. Search History
Use the search box to find prompts by keywords or content.

### 4. Clean Up Regularly
Periodically clear old or unnecessary prompts to keep the list manageable.

### 5. Hide When Not Needed
Toggle the sidebar off (◀) to maximize workspace for long prompts.

## Privacy & Security

- All data is stored **locally** on your machine
- No cloud synchronization
- History file is plain JSON and can be manually edited
- Clear history anytime to remove all stored prompts

## Troubleshooting

### Sidebar Not Showing
- Click the ▶ button on the left edge to show sidebar
- Check if `sidebar_visible` setting is enabled

### History Not Loading
- Verify `~/.promptc_history.json` exists and is valid JSON
- Check file permissions
- Click "🔄 Refresh" to reload

### Items Not Appearing
- Check search filter - clear it to see all items
- Verify prompt was generated (history saves on generate)
- Check if history limit (100 items) was reached

### Cannot Delete Items
- Ensure item is selected (highlighted)
- Try right-click → Delete instead of Delete key
- Check file write permissions

## Technical Details

### History Limit
- Maximum 100 items stored
- Oldest items automatically removed when limit reached
- Most recent prompts appear at top

### Preview Length
- Preview shows first 100 characters
- Newlines replaced with spaces
- "..." added if prompt is longer

### File Format
- UTF-8 encoded JSON
- Human-readable and editable
- Automatic backup on save (by OS)

## Version History

### v2.0.40 (November 5, 2025)
- ✅ Initial release
- ✅ Recent prompts list with search
- ✅ Favorites system with star icons
- ✅ Context menu (Load, Delete, Toggle Favorite)
- ✅ Keyboard shortcuts (Enter, Delete)
- ✅ Toggle sidebar visibility
- ✅ Auto-save on generate
- ✅ 100 item history limit

## Related Features
- [Template Gallery](TEMPLATE_GALLERY.md) - Pre-built prompt templates
- [Drag & Drop](DRAG_DROP_GUIDE.md) - Load prompts from files
- [UI Themes](../README.md#themes) - Light/dark mode support

---

**Need Help?** Open an issue on GitHub or check the main README.md
