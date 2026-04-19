#!/bin/bash

# Configuration
POLL_INTERVAL=10 # Check every 10 seconds

echo "Starting Git Auto-Push Watcher..."
echo "Press Ctrl+C to stop."

while true; do
    # Check if there are any uncommitted changes
    if [[ -n $(git status -s) ]]; then
        echo "Changes detected! Committing and pushing..."
        
        # Add all changes
        git add .
        
        # Commit with the current timestamp
        git commit -m "Auto-commit: $(date +'%Y-%m-%d %H:%M:%S')"
        
        # Push to the current branch
        git push
        
        echo "Push complete. Resuming watch..."
    fi
    
    # Wait before checking again
    sleep $POLL_INTERVAL
done
