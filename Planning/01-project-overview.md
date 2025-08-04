# Squarespace Blog Archiver - Project Overview

## Purpose

Archive and preserve content from the Squarespace blog at https://www.thelibrarianedge.com/ for backup/preservation purposes and potential future migration to other platforms.

## Primary Goals

- **Backup & Preservation**: Ensure the blog content is never lost
- **Future Migration Ready**: Create portable formats that can be imported into various platforms
- **Multiple Output Formats**: Generate JSON, Markdown, and static HTML archives
- **Comprehensive Coverage**: Capture blog posts, metadata, images, and site structure

## Target Outputs

### 1. JSON Archive

- Structured data with full metadata
- Easy to programmatically process
- Includes post content, dates, categories, tags, author info
- Image URLs and alt text preserved

### 2. Markdown Archive

- Human-readable format
- Perfect for static site generators (Jekyll, Hugo, Gatsby)
- Preserves formatting and links
- Compatible with most blogging platforms

### 3. Static HTML Archive

- Complete offline browsable version
- Preserved CSS styling and layout
- Local copies of images and assets
- Self-contained backup that works without internet

## Technical Constraints

- Must respect the site's terms of service (user owns the content)
- Should be gentle on server resources (appropriate delays)
- Handle dynamic content that requires JavaScript rendering
- Robust error handling for network issues
- Preserve original publish dates and URL structures where possible
