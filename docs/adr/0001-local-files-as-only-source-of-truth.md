# Local files are the only source of truth

Applications are tracked as folders and Markdown files under `generated_cvs/`, with no database. A minimal local server (single Python stdlib script) serves the board and only reads and writes those files. A static page alone could not write files from `file://`, and the File System Access API is Chromium-only and awkward across WSL, so a tiny server was the trade-off. This retires the old SQLite pipeline (`jobs.db`), whose separate status would compete with the board.
