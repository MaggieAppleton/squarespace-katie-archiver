"""Markdown generator for blog posts."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
from bs4 import BeautifulSoup
import html2text

from .config import ArchiveConfig


class MarkdownGenerator:
    """Generates Markdown files from extracted blog posts."""
    
    def __init__(self, config: ArchiveConfig):
        self.config = config
        self.logger = logging.getLogger("squarespace_archiver.markdown_generator")
        
        # Configure html2text converter
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # Don't wrap lines
        self.html_converter.unicode_snob = True
        self.html_converter.escape_snob = True
    
    def generate_markdown_files(self, posts: List[Dict[str, Any]], output_dir: Path) -> Dict[str, Any]:
        """Generate Markdown files for all posts."""
        self.logger.info(f"Generating Markdown files for {len(posts)} posts...")
        
        # Create output directory
        markdown_dir = Path(output_dir) / "markdown"
        markdown_dir.mkdir(parents=True, exist_ok=True)
        
        generated_files = []
        errors = []
        
        for post in posts:
            try:
                markdown_file = self._generate_single_markdown(post, markdown_dir)
                if markdown_file:
                    generated_files.append(str(markdown_file))
                    self.logger.debug(f"Generated: {markdown_file}")
                else:
                    errors.append(f"Failed to generate markdown for post: {post.get('title', 'Unknown')}")
                    
            except Exception as e:
                error_msg = f"Error generating markdown for post {post.get('id', 'unknown')}: {e}"
                errors.append(error_msg)
                self.logger.error(error_msg)
        
        # Generate index files
        self._generate_markdown_index(posts, markdown_dir)
        
        results = {
            "markdown_directory": str(markdown_dir),
            "total_posts": len(posts),
            "successful_files": len(generated_files),
            "failed_files": len(errors),
            "generated_files": generated_files,
            "errors": errors
        }
        
        self.logger.info(f"Markdown generation complete:")
        self.logger.info(f"  Generated: {len(generated_files)} files")
        self.logger.info(f"  Errors: {len(errors)}")
        self.logger.info(f"  Output directory: {markdown_dir}")
        
        return results
    
    def _generate_single_markdown(self, post: Dict[str, Any], output_dir: Path) -> Optional[Path]:
        """Generate a single Markdown file for a post."""
        
        # Generate filename based on date and slug
        filename = self._generate_filename(post)
        if not filename:
            return None
        
        markdown_file = output_dir / f"{filename}.md"
        
        try:
            # Generate frontmatter
            frontmatter = self._generate_frontmatter(post)
            
            # Convert content to markdown
            content = self._convert_content_to_markdown(post)
            
            # Combine frontmatter and content
            full_content = f"---\n{frontmatter}\n---\n\n{content}"
            
            # Write to file
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            return markdown_file
            
        except Exception as e:
            self.logger.error(f"Failed to generate markdown file {markdown_file}: {e}")
            return None
    
    def _generate_filename(self, post: Dict[str, Any]) -> Optional[str]:
        """Generate filename for markdown file."""
        
        # Try to get date from post
        date_str = post.get('published_date', '')
        slug = post.get('slug', '')
        post_id = post.get('id', '')
        
        if date_str:
            try:
                # Extract date part (YYYY-MM-DD)
                date_part = date_str[:10]  # ISO format YYYY-MM-DD
                
                if slug:
                    return f"{date_part}-{slug}"
                elif post_id:
                    return f"{date_part}-{post_id}"
                else:
                    # Use title as fallback
                    title = post.get('title', '')
                    if title:
                        clean_title = self._slugify(title)
                        return f"{date_part}-{clean_title}"
                    
            except Exception as e:
                self.logger.debug(f"Error parsing date {date_str}: {e}")
        
        # Fallback to slug or ID
        if slug:
            return slug
        elif post_id:
            return post_id
        else:
            # Last resort: slugified title
            title = post.get('title', 'untitled')
            return self._slugify(title)
    
    def _generate_frontmatter(self, post: Dict[str, Any]) -> str:
        """Generate YAML frontmatter for the post."""
        
        # Basic metadata
        frontmatter_data = {
            'title': post.get('title', ''),
            'date': post.get('published_date', ''),
            'author': post.get('author', ''),
            'layout': 'post'  # Standard Jekyll/Hugo layout
        }
        
        # Add optional fields if they exist
        if post.get('excerpt'):
            frontmatter_data['excerpt'] = post['excerpt']
        
        if post.get('meta_description'):
            frontmatter_data['description'] = post['meta_description']
        
        # Categories and tags
        categories = post.get('categories', [])
        if categories:
            frontmatter_data['categories'] = categories
        
        tags = post.get('tags', [])
        if tags:
            frontmatter_data['tags'] = tags
        
        # Original URL for reference
        if post.get('url'):
            frontmatter_data['original_url'] = post['url']
        
        # Slug for pretty URLs
        if post.get('slug'):
            frontmatter_data['slug'] = post['slug']
        
        # Word count
        word_count = post.get('word_count', 0)
        if word_count:
            frontmatter_data['word_count'] = word_count
        
        # Image count
        images = post.get('images', [])
        if images:
            frontmatter_data['image_count'] = len(images)
            # Add featured image if available
            if images[0].get('original_url'):
                frontmatter_data['featured_image'] = images[0]['original_url']
        
        # Archive metadata
        frontmatter_data['archived_date'] = datetime.now().strftime('%Y-%m-%d')
        
        # Convert to YAML
        return yaml.dump(frontmatter_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    def _convert_content_to_markdown(self, post: Dict[str, Any]) -> str:
        """Convert post content to clean Markdown."""
        
        # Try different content sources in order of preference
        html_content = post.get('content_html', '')
        existing_markdown = post.get('content_markdown', '')
        text_content = post.get('content_text', '')
        
        if html_content:
            # Convert HTML to Markdown
            markdown_content = self._html_to_markdown(html_content)
        elif existing_markdown:
            # Use existing markdown
            markdown_content = existing_markdown
        elif text_content:
            # Use plain text as fallback
            markdown_content = text_content
        else:
            markdown_content = "*No content available*"
        
        # Clean up the markdown
        markdown_content = self._clean_markdown(markdown_content)
        
        # Add images section if there are images
        images = post.get('images', [])
        if images:
            markdown_content += self._generate_images_section(images)
        
        # Add links section if there are external links
        links = post.get('links', [])
        external_links = [link for link in links if link.get('type') == 'external']
        if external_links:
            markdown_content += self._generate_links_section(external_links)
        
        return markdown_content
    
    def _html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to clean Markdown."""
        
        # First, clean up the HTML
        cleaned_html = self._clean_html(html_content)
        
        # Convert to markdown using html2text
        markdown = self.html_converter.handle(cleaned_html)
        
        return markdown
    
    def _clean_html(self, html_content: str) -> str:
        """Clean HTML content before conversion."""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'meta', 'link']):
            element.decompose()
        
        # Clean up common Squarespace-specific elements
        for element in soup.select('[class*="sqs-"]'):
            # Keep content but remove Squarespace-specific classes
            if element.name:
                element.attrs = {k: v for k, v in element.attrs.items() if not k.startswith('data-')}
        
        # Convert relative URLs to absolute
        base_url = self.config.site_url
        
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('/'):
                img['src'] = base_url.rstrip('/') + src
        
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and href.startswith('/'):
                link['href'] = base_url.rstrip('/') + href
        
        return str(soup)
    
    def _clean_markdown(self, markdown_content: str) -> str:
        """Clean up converted Markdown content."""
        
        # Remove excessive blank lines
        markdown_content = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown_content)
        
        # Clean up list formatting
        markdown_content = re.sub(r'\n\s*\n(\s*[-*+])', r'\n\1', markdown_content)
        
        # Fix heading spacing
        markdown_content = re.sub(r'\n(#{1,6}\s+)', r'\n\n\1', markdown_content)
        
        # Remove trailing whitespace
        lines = markdown_content.split('\n')
        lines = [line.rstrip() for line in lines]
        markdown_content = '\n'.join(lines)
        
        return markdown_content.strip()
    
    def _generate_images_section(self, images: List[Dict[str, Any]]) -> str:
        """Generate a markdown section for images."""
        
        if not images:
            return ""
        
        section = "\n\n---\n\n## Images\n\n"
        
        for i, img in enumerate(images, 1):
            url = img.get('original_url', '')
            alt_text = img.get('alt_text', f'Image {i}')
            caption = img.get('caption', '')
            
            if url:
                section += f"![{alt_text}]({url})\n"
                if caption:
                    section += f"*{caption}*\n"
                section += "\n"
        
        return section
    
    def _generate_links_section(self, links: List[Dict[str, Any]]) -> str:
        """Generate a markdown section for external links."""
        
        if not links:
            return ""
        
        section = "\n\n---\n\n## External Links\n\n"
        
        for link in links:
            url = link.get('url', '')
            text = link.get('text', url)
            
            if url:
                section += f"- [{text}]({url})\n"
        
        return section
    
    def _generate_markdown_index(self, posts: List[Dict[str, Any]], output_dir: Path) -> None:
        """Generate index files for the Markdown collection."""
        
        # Generate README.md with overview
        readme_content = self._generate_readme(posts)
        with open(output_dir / "README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        # Generate _config.yml for Jekyll compatibility
        config_content = self._generate_jekyll_config()
        with open(output_dir / "_config.yml", 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        self.logger.info("Generated Markdown index files: README.md, _config.yml")
    
    def _generate_readme(self, posts: List[Dict[str, Any]]) -> str:
        """Generate README.md for the Markdown collection."""
        
        total_posts = len(posts)
        total_words = sum(post.get('word_count', 0) for post in posts)
        
        # Get date range
        dates = [post.get('published_date', '') for post in posts if post.get('published_date')]
        dates.sort()
        
        earliest = dates[0][:10] if dates else "Unknown"
        latest = dates[-1][:10] if dates else "Unknown"
        
        readme = f"""# The Librarian Edge - Blog Archive (Markdown)

This directory contains the complete blog archive in Markdown format, suitable for static site generators like Jekyll, Hugo, or Gatsby.

## Archive Statistics

- **Total Posts**: {total_posts:,}
- **Total Words**: {total_words:,}
- **Date Range**: {earliest} to {latest}
- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## File Organization

Each blog post is saved as an individual Markdown file with the naming convention:
`YYYY-MM-DD-post-slug.md`

### Frontmatter

Each Markdown file includes YAML frontmatter with the following fields:

```yaml
title: "Post Title"
date: "2019-10-26T00:00:00"
author: "Katie Day"
layout: post
categories: ["Category Name"]
tags: ["tag1", "tag2"]
original_url: "https://www.thelibrarianedge.com/libedge/..."
slug: "post-slug"
word_count: 1234
image_count: 5
featured_image: "https://images.squarespace-cdn.com/..."
archived_date: "{datetime.now().strftime('%Y-%m-%d')}"
```

## Usage with Static Site Generators

### Jekyll

This collection is ready to use with Jekyll:

1. Copy the Markdown files to your `_posts` directory
2. Use the included `_config.yml` as a starting point
3. Run `bundle exec jekyll serve`

### Hugo

For Hugo:

1. Copy files to `content/posts/`
2. Update frontmatter format if needed (Hugo uses TOML/YAML)
3. Run `hugo server`

### Gatsby

For Gatsby with gatsby-source-filesystem:

1. Place files in your content directory
2. Configure the source plugin to read from this directory
3. Use GraphQL queries to access the frontmatter

## Content Processing

- **HTML to Markdown**: Original HTML content has been converted to clean Markdown
- **Image References**: Images are referenced by their original URLs
- **Link Preservation**: All internal and external links are preserved
- **Metadata**: Complete metadata including categories, tags, and publication dates

## File Structure

```
markdown/
├── README.md (this file)
├── _config.yml (Jekyll configuration)
├── 2019-10-26-singapore-red-dots.md
├── 2019-05-18-the-difficulty-in-delivering-booklists.md
├── 2018-01-05-prizing-balance.md
└── ... (additional posts)
```

Generated by Squarespace Blog Archiver v0.1.0
"""
        
        return readme
    
    def _generate_jekyll_config(self) -> str:
        """Generate basic Jekyll configuration."""
        
        config = f"""# Jekyll Configuration for The Librarian Edge Archive
# Generated by Squarespace Blog Archiver

title: "The Librarian Edge - Archive"
description: "Complete archive of The Librarian Edge blog"
baseurl: ""
url: ""

# Build settings
markdown: kramdown
highlighter: rouge
theme: minima

# Plugins
plugins:
  - jekyll-feed
  - jekyll-sitemap
  - jekyll-seo-tag

# Collections
collections:
  posts:
    output: true
    permalink: /:year/:month/:day/:title/

# Defaults
defaults:
  - scope:
      path: ""
      type: "posts"
    values:
      layout: "post"
      author: "Katie Day"

# Exclude files
exclude:
  - README.md
  - Gemfile
  - Gemfile.lock
  - node_modules
  - vendor

# Archive metadata
archive:
  generated_date: "{datetime.now().strftime('%Y-%m-%d')}"
  source: "https://www.thelibrarianedge.com/"
  generator: "Squarespace Blog Archiver v0.1.0"
"""
        
        return config
    
    def _slugify(self, text: str) -> str:
        """Convert text to a URL-friendly slug."""
        
        # Convert to lowercase
        slug = text.lower()
        
        # Replace spaces and special characters with hyphens
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        # Limit length
        if len(slug) > 50:
            slug = slug[:50].rstrip('-')
        
        return slug or 'untitled'