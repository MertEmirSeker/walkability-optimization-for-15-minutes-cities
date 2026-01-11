#!/bin/bash
# Simple progress checker - Terminal olmadan kullanabilirsin!

LOG_FILE="pipeline_run.log"
OUTPUT_FILE="progress_status.txt"

while true; do
    clear
    echo "====================================" > $OUTPUT_FILE
    echo "WALKABILITY OPTIMIZATION - PROGRESS" >> $OUTPUT_FILE
    echo "====================================" >> $OUTPUT_FILE
    echo "" >> $OUTPUT_FILE
    
    # Check if process is running
    if ps aux | grep -q "[p]ython.*src.main"; then
        echo "Status: ✅ RUNNING" >> $OUTPUT_FILE
    else
        echo "Status: ✅ COMPLETED or ❌ STOPPED" >> $OUTPUT_FILE
    fi
    
    echo "" >> $OUTPUT_FILE
    
    # Get current progress
    PROGRESS=$(tail -3 $LOG_FILE 2>/dev/null | grep -oP '\d+\.\d+%' | tail -1)
    if [ ! -z "$PROGRESS" ]; then
        echo "Progress: $PROGRESS" >> $OUTPUT_FILE
        
        # Get ETA
        ETA=$(tail -3 $LOG_FILE 2>/dev/null | grep -oP 'ETA: \d+s' | tail -1)
        if [ ! -z "$ETA" ]; then
            SECONDS=$(echo $ETA | grep -oP '\d+')
            MINUTES=$((SECONDS / 60))
            echo "Time remaining: ~$MINUTES minutes" >> $OUTPUT_FILE
        fi
    fi
    
    echo "" >> $OUTPUT_FILE
    echo "Last updated: $(date '+%H:%M:%S')" >> $OUTPUT_FILE
    echo "====================================" >> $OUTPUT_FILE
    
    # Show the file
    cat $OUTPUT_FILE
    
    sleep 10
done
