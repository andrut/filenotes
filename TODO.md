- Work on portability to Mac and Windows
    - macOS: image capture done (screencapture for -S/-R; pngpaste→osascript for -C). Region (-R) still needs a manual interactive test.
    - Windows: still unsupported (no capture backend).
- GUI tool
    I'm thinking of creating a GUI tool for making notes from outside of terminal level. Context folder/file would be the one we just worked on with the main tool. It would allow adding 
- Notes as hidden files (.file...md) - by default off, setable in tools config.
- ls-notes:
    -- DONE -ss / --super-short - one line per file with a floor-rounded age (12s/47m/1h/3d/1w/1mo/1y)
- Lib for using notes in program:
	- prompting note on some file - user has to provide note on the file that program just created
	- reading notes from files that we open
	- opening file by looking for file that has some phrase in the note



maybies:
- Right now there is this option to embed images inside md files. Right now images are embedded right inline where image should be as base64 block of text. I saw an interesting way to embed images that google drive uses when I'm exporting textdocument to md file. It uses reference "image1", "image2", etc... inline inside the text and then puts said images embedded at the end of the file. vs code, typora and other markdown editors/viewers opened such files without a problem. Do you know this method of embedding images? 
    - maybe not, since that would conflict with simple nature of concatenating notes to md file...