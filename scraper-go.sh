#!/usr/bin/env bash

# Configuration
SERVER_URL="https://scraper-751660269987.us-central1.run.app"
SCRAPER_CMD="poetry run scraper scrape"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Header
echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}       MD Scraper Interactive CLI (Remote)       ${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "Using Server: ${YELLOW}$SERVER_URL${NC}\n"

# 2. Input
echo -e "Enter ${GREEN}URL(s)${NC} (space separated) or a ${GREEN}file path${NC} (.txt with URLs):"
read -r USER_INPUT

# Parse Input
URLS=()
if [ -f "$USER_INPUT" ]; then
    echo -e "Processing batch file: $USER_INPUT..."
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        [[ -z "$line" || "$line" =~ ^# ]] && continue
        URLS+=("$line")
    done < "$USER_INPUT"
else
    # Split by space
    IFS=' ' read -r -a URLS <<< "$USER_INPUT"
fi

URL_COUNT=${#URLS[@]}
if [ "$URL_COUNT" -eq 0 ]; then
    echo "No valid URLs found. Exiting."
    exit 1
fi

echo -e "Found ${GREEN}$URL_COUNT${NC} URL(s) to process."

# Function to sanitize filename
sanitize_filename() {
    echo "$1" | sed 's/[^a-zA-Z0-9._-]/_/g' | cut -c 1-50
}

# Function to extract title from Markdown content
get_title() {
    local content="$1"
    local url="$2"
    # Try to find first H1 header
    local title=$(echo "$content" | grep -m 1 "^# ") | sed 's/^# //'
    
    # If no H1, try H2
    if [ -z "$title" ]; then
        title=$(echo "$content" | grep -m 1 "^## ") | sed 's/^## //'
    fi

    # Fallback to domain/path if no header found
    if [ -z "$title" ]; then
        # Extract domain and last segment
        title=$(echo "$url" | awk -F/ '{print $3 "_" $NF}')
    fi
    
    # Fallback if that failed (e.g. root domain)
    if [ -z "$title" ] || [ "$title" == "_" ]; then
        title="scraped_page_$(date +%s)"
    fi

    sanitize_filename "$title"
}

# 3. Single URL Logic
if [ "$URL_COUNT" -eq 1 ]; then
    TARGET_URL="${URLS[0]}"
    echo -e "\nTarget: $TARGET_URL"
    echo "Choose output format:"
    echo "1) Print to Terminal"
    echo "2) Save to File"
    read -p "Select (1/2): " CHOICE

    echo -e "\n${YELLOW}Scraping...${NC}"
    CONTENT=$($SCRAPER_CMD "$TARGET_URL" --server "$SERVER_URL")

    if [ "$CHOICE" == "1" ]; then
        echo -e "\n${BLUE}--- START OUTPUT ---${NC}"
        echo "$CONTENT"
        echo -e "${BLUE}--- END OUTPUT ---${NC}"
    else
        read -p "Enter filename (default: auto-detect): " CUSTOM_NAME
        
        if [ -z "$CUSTOM_NAME" ]; then
            TITLE=$(get_title "$CONTENT" "$TARGET_URL")
            FILENAME="${TITLE}.md"
        else
            FILENAME="$CUSTOM_NAME"
        fi

        echo "$CONTENT" > "$FILENAME"
        echo -e "${GREEN}Success!${NC} Saved to: $FILENAME"
    fi

# 4. Multiple URL Logic
else
    echo -e "\nChoose output location:"
    echo "1) Save in Current Directory"
    echo "2) Create New Directory"
    read -p "Select (1/2): " LOC_CHOICE

    OUTPUT_DIR="."
    if [ "$LOC_CHOICE" == "2" ]; then
        read -p "Enter new directory name: " DIR_NAME
        mkdir -p "$DIR_NAME"
        OUTPUT_DIR="$DIR_NAME"
        echo -e "Created directory: ${BLUE}$OUTPUT_DIR${NC}"
    fi

    echo -e "\nStarting Batch Process..."
    
    CURRENT=1
    for URL in "${URLS[@]}"; do
        echo -ne "[${CURRENT}/${URL_COUNT}] Scraping ${YELLOW}$URL${NC} ... "
        
        # Scrape
        CONTENT=$($SCRAPER_CMD "$URL" --server "$SERVER_URL")
        
        # Determine Filename
        TITLE=$(get_title "$CONTENT" "$URL")
        FILENAME="${OUTPUT_DIR}/${TITLE}.md"
        
        # Save
        echo "$CONTENT" > "$FILENAME"
        echo -e "${GREEN}Done${NC} -> $FILENAME"
        
        ((CURRENT++))
    done
    
    echo -e "\n${GREEN}Batch processing complete!${NC}"
fi
