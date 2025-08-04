# Squarespace Blog Archiver

A comprehensive Python tool for archiving and preserving Squarespace blog content in multiple formats for backup and future migration.

## Overview

This tool scrapes content from a Squarespace blog and generates three different archive formats:

- **JSON**: Structured data for programmatic use
- **Markdown**: Human-readable format compatible with static site generators
- **Static HTML**: Complete offline browsable archive with preserved styling

## Target Site

- **URL**: https://www.thelibrarianedge.com/
- **Purpose**: Backup and preservation of blog content
- **Owner**: Content owner (authorized access)

## Project Structure

```
squarespace-blog-archiver/
├── Planning/                    # Project planning documents
│   ├── 01-project-overview.md
│   ├── 02-technical-requirements.md
│   └── 03-implementation-plan.md
├── src/                         # Source code
├── output/                      # Generated archives
│   ├── json/
│   ├── markdown/
│   └── html/
└── requirements.txt            # Python dependencies
```

## Quick Start

```bash
# Clone and setup
cd ~/Github/squarespace-blog-archiver
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the archiver (once implemented)
python src/main.py --url https://www.thelibrarianedge.com/
```

## Documentation

Detailed planning and technical documentation is available in the `Planning/` directory:

- Project overview and goals
- Technical requirements and architecture
- Phased implementation plan with checklists
