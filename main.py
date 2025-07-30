from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup
import requests
import re
import random
import time
from urllib.parse import quote
import json

app = Flask(__name__)

# User Agent List
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def extract_colors_from_text(text):
    """Extract color code from text"""
    # Match hexadecimal color code
    hex_colors = re.findall(r'#(?:[0-9a-fA-F]{3}){1,2}\b', text)
    # Match rgb/rgba color
    rgb_colors = re.findall(r'rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)', text)
    # Match color names
    color_names = re.findall(r'\b(?:red|green|blue|yellow|orange|purple|pink|brown|black|white|gray|grey|cyan|magenta|violet|gold|silver|lavender|lime|teal|indigo|maroon|olive|navy|azure|beige|coral|cream|emerald|fuchsia|ivory|khaki|salmon|tan|turquoise)\b', text, re.IGNORECASE)
    
    return hex_colors + rgb_colors + [name.lower() for name in color_names]

def extract_color_palettes(soup):
    """Extract a color scheme from a page"""
    palettes = []
    
    # Find possible color scheme containers
    palette_containers = soup.find_all(class_=re.compile(r'palette|color-group|swatches|colors|scheme|combination'))
    
    for container in palette_containers:
        # Extract color elements
        color_elements = container.find_all(class_=re.compile(r'color|swatch|chip|sample'))
        
        # If there is no specific class, try to find elements with background color
        if not color_elements:
            color_elements = container.find_all(style=re.compile(r'background-color|color'))
        
        colors = []
        for element in color_elements:
            # Get color from style attribute
            if 'style' in element.attrs:
                bg_match = re.search(r'background-color:\s*(.*?)[;]', element['style'])
                if bg_match:
                    colors.append(bg_match.group(1).strip())
                else:
                    color_match = re.search(r'color:\s*(.*?)[;]', element['style'])
                    if color_match:
                        colors.append(color_match.group(1).strip())
            
            # Get color from data attribute
            elif 'data-color' in element.attrs:
                colors.append(element['data-color'])
            
            # Get color from text
            else:
                text_colors = extract_colors_from_text(element.get_text())
                if text_colors:
                    colors.extend(text_colors)
        
        # If 3—8 colors are found, it is considered as an effective color scheme
        if 3 <= len(colors) <= 8:
            palettes.append(colors)
    
    return palettes

def search_google_for_palettes(keyword):
    """Using Google to search for color schemes"""
    try:
        query = f"{keyword} color palette site:coolors.co OR site:colorhunt.co OR site:colordesigner.io OR site:schecolor.com"
        url = f"https://www.google.com/search?q={quote(query)}"
        
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        
        # Extract the first 5 related links
        for result in soup.select('.tF2Cxc')[:5]:
            link = result.a['href']
            if link.startswith('http'):
                links.append(link)
        
        return links
    except Exception as e:
        print(f"Google search error: {e}")
        return []

def crawl_palette_sites(keyword):
    """Crawling color scheme website"""
    sites = [
        {
            'url': f'https://coolors.co/palettes/search/{keyword}',
            'type': 'coolors'
        },
        {
            'url': f'https://colorhunt.co/palettes/{keyword}',
            'type': 'colorhunt'
        },
        {
            'url': f'https://www.colorhexa.com/color-{keyword}',
            'type': 'colorhexa'
        },
        {
            'url': f'https://www.color-name.com/{keyword}-color',
            'type': 'colorname'
        },
        {
            'url': f'https://www.design-seeds.com/search/{keyword}/',
            'type': 'designseeds'
        },
        {
            'url': f'https://www.schemecolor.com/s/{keyword}',
            'type': 'schemecolor'
        },
        {
            'url': f'https://www.colorcombos.com/color-schemes.html?search={keyword}',
            'type': 'colorcombos'
        }
    ]
    
    # Add a link found by Google Search
    google_links = search_google_for_palettes(keyword)
    for i, link in enumerate(google_links[:3]):
        sites.append({
            'url': link,
            'type': f'google_result_{i}'
        })
    
    all_palettes = []
    
    for site in sites:
        try:
            headers = {
                'User-Agent': get_random_user_agent(),
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/'
            }
            
            print(f"Fetching: {site['url']}")
            response = requests.get(site['url'], headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Different extraction strategies are adopted according to different website types
            if site['type'] == 'coolors':
                palette_divs = soup.select('.palette_container')
                for div in palette_divs:
                    colors = []
                    color_divs = div.select('.palette_color')
                    for color_div in color_divs:
                        hex_code = color_div.get('data-hex')
                        if hex_code:
                            colors.append(f'#{hex_code}')
                    if colors:
                        all_palettes.append(colors)
            
            elif site['type'] == 'colorhunt':
                palette_divs = soup.select('.palette')
                for div in palette_divs:
                    colors = []
                    color_divs = div.select('.color')
                    for color_div in color_divs:
                        if 'style' in color_div.attrs:
                            bg_color = re.search(r'background-color:\s*(.*?)[;]', color_div['style'])
                            if bg_color:
                                colors.append(bg_color.group(1).strip())
                    if colors:
                        all_palettes.append(colors)
            
            elif site['type'] == 'colorhexa':
                color_table = soup.select('.color-table tbody tr')
                if color_table:
                    palette = []
                    for row in color_table[:8]:  # Take up to 8 colors
                        hex_code = row.select_one('td:nth-child(2)').get_text(strip=True)
                        if hex_code:
                            palette.append(f'#{hex_code}')
                    if palette:
                        all_palettes.append(palette)
            
            elif site['type'] == 'schemecolor':
                palette_divs = soup.select('.palette-container')
                for div in palette_divs:
                    colors = []
                    color_divs = div.select('.palette-color')
                    for color_div in color_divs:
                        hex_code = color_div.find(class_='hexcode').get_text(strip=True)
                        if hex_code:
                            colors.append(f'#{hex_code}')
                    if colors:
                        all_palettes.append(colors)
            
            # General extraction method
            extracted = extract_color_palettes(soup)
            all_palettes.extend(extracted)
            
            time.sleep(random.uniform(1, 3))  # random latency
            
        except Exception as e:
            print(f"Error crawling {site['url']}: {str(e)}")
            continue
    
    return all_palettes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_palettes', methods=['POST'])
def get_palettes():
    keyword = request.form.get('keyword', '').strip().lower()
    if not keyword:
        return jsonify({'error': 'Please enter a keyword'})
    
    try:
        palettes = crawl_palette_sites(keyword)
        
        if not palettes:
            return jsonify({
                'error': f'No color palettes found for "{keyword}". Try another word like "happy", "ocean" or "vintage".'
            })
        
        # Remove duplicates
        unique_palettes = []
        seen = set()
        for palette in palettes:
            palette_tuple = tuple(palette)
            if palette_tuple not in seen:
                seen.add(palette_tuple)
                unique_palettes.append(palette)
        
        return jsonify({
            'keyword': keyword,
            'palettes': unique_palettes[:5]  # Return to up to 5 unique color schemes
        })
    
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)