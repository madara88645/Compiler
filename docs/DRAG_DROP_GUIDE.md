# Drag & Drop Feature Guide

## 📁 Drag & Drop File Loading

The UI now supports drag and drop functionality for easily loading prompt and context text from files!

### How to Use

#### Method 1: Drag & Drop
1. Open a text file in your file explorer
2. Drag the file over the **Prompt** or **Context** text area
3. You'll see a blue highlighted drop zone with the message "📁 Drop file here..."
4. Release the file to load its contents

#### Method 2: Load Button
- Click the **📂 Load** button next to Prompt or Context labels
- Select a file from the file dialog
- The contents will be loaded into the text area

### Supported File Types
- `.txt` - Plain text files
- `.md` / `.markdown` - Markdown files
- `.text` - Text files

### Features

✨ **Visual Feedback:**
- Drop zone highlights in blue when dragging files
- Shows which area will receive the file (prompt or context)
- Animated indicators and messages

🔒 **Safety:**
- Asks for confirmation before replacing existing content
- Shows file info (name, size, line count) after loading
- Error messages if file format is unsupported

📊 **Auto-Update:**
- Automatically updates character/word/token counts
- Maintains formatting and line breaks
- UTF-8 encoding support

### Tips

💡 **Quick Workflow:**
1. Drag your prompt file to the Prompt area
2. Drag reference material to the Context area
3. Click **⚡ Generate** (or press Ctrl+Enter)

💡 **Multiple Files:**
- Currently loads one file at a time
- Drop additional files to replace content (with confirmation)

💡 **Examples:**
- Try dragging files from the `examples/` folder
- Works great with saved prompts and templates

### Keyboard Shortcuts

- `Ctrl+Enter` or `F5` - Generate
- `Ctrl+S` - Save outputs
- `Ctrl+F` - Find in active tab

### Troubleshooting

**Drag & drop not working?**
- Use the **📂 Load** button as fallback
- Some Linux systems may require tkinterdnd2 package: `pip install tkinterdnd2`
- Windows and macOS support built-in

**File won't load?**
- Check file encoding (must be UTF-8)
- Verify file extension is supported (.txt, .md)
- Check file permissions

### Technical Details

The drag & drop implementation:
- Uses native tkinter DND support on Windows/macOS
- Falls back to tkinterdnd2 if available on Linux
- Provides manual file dialog as universal fallback
- Thread-safe file reading
- Proper error handling and user feedback

---

Enjoy the enhanced workflow! 🎉
