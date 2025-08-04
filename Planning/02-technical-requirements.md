# Technical Requirements

## Architecture Overview

A Python-based web scraping tool that generates multiple output formats from a single scraping session.

## Core Technologies

### Primary Tools

- **Python 3.8+** - Main programming language
- **Playwright** - Browser automation for JavaScript-rendered content
- **BeautifulSoup4** - HTML parsing and content extraction
- **Requests** - HTTP client for direct downloads
- **Pathlib** - File system operations

### Data Processing

- **JSON** - Built-in Python library for structured data
- **Markdown** - `python-markdown` for conversion and validation
- **HTML/CSS** - Template-based generation with preserved styling

### Additional Libraries

- **Pillow** - Image processing and optimization
- **python-dateutil** - Date parsing and formatting
- **urllib** - URL handling and validation
- **logging** - Comprehensive operation logging

## Data Structure Design

### Core Data Model

```json
{
	"site_metadata": {
		"title": "The Librarian Edge",
		"url": "https://www.thelibrarianedge.com/",
		"scraped_date": "2024-01-15T10:30:00Z",
		"total_posts": 42
	},
	"posts": [
		{
			"id": "unique-post-id",
			"title": "Post Title",
			"slug": "post-url-slug",
			"content_html": "<p>Original HTML content</p>",
			"content_markdown": "# Converted markdown content",
			"excerpt": "Brief summary...",
			"published_date": "2023-05-15T14:30:00Z",
			"modified_date": "2023-05-16T09:15:00Z",
			"categories": ["Technology", "Libraries"],
			"tags": ["tools", "productivity"],
			"images": [
				{
					"src": "local/path/to/image.jpg",
					"original_url": "https://example.com/image.jpg",
					"alt_text": "Description",
					"caption": "Image caption"
				}
			],
			"links": ["https://external-link.com"]
		}
	],
	"assets": {
		"images": ["list of downloaded image files"],
		"css": ["preserved stylesheets"],
		"js": ["necessary JavaScript files"]
	}
}
```

## Output Specifications

### 1. JSON Archive

- **Location**: `output/archive.json`
- **Format**: Pretty-printed, UTF-8 encoded
- **Validation**: JSON schema validation
- **Backup**: Timestamped copies for each run

### 2. Markdown Archive

- **Structure**: `output/markdown/YYYY-MM-DD-post-slug.md`
- **Frontmatter**: YAML metadata block
- **Content**: Clean markdown with preserved formatting
- **Images**: Relative links to local copies

### 3. Static HTML Archive

- **Structure**: Mirrored directory structure
- **Index**: Generated table of contents
- **Styling**: Preserved original CSS with fallbacks
- **Navigation**: Inter-post linking preserved

## Performance Requirements

- **Respectful Scraping**: 2-3 second delays between requests
- **Memory Efficient**: Stream processing for large content
- **Resumable**: Can continue from interruptions
- **Progress Tracking**: Real-time status updates
- **Error Recovery**: Retry failed downloads with exponential backoff

## Quality Assurance

- **Content Validation**: Verify all posts scraped successfully
- **Link Checking**: Validate internal and external links
- **Image Verification**: Confirm all images downloaded
- **Format Testing**: Validate JSON, Markdown, and HTML outputs
- **Diff Reporting**: Compare against previous runs to detect changes
