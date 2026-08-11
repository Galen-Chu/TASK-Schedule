"""Generic Obsidian markdown note writer.

Each report builds its full markdown (frontmatter + body) and hands the string
here; this module only owns directory creation + file writing, so the path
handling is identical across reports.
"""
import os


def write_note(output_dir, filename, content):
    """Write ``content`` to ``output_dir/filename``. Returns the full path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
