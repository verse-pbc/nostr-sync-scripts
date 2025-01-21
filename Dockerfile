FROM python:3.11-slim

# Install cron and required packages
RUN apt-get update && apt-get install -y \
    cron \
    wget \
    python3-venv \
    pkg-config \
    libsecp256k1-dev \
    gcc \
    make \
    && rm -rf /var/lib/apt/lists/*

# Download and install nak binary
RUN wget https://github.com/fiatjaf/nak/releases/download/v0.10.1/nak-v0.10.1-linux-amd64 -O /usr/local/bin/nak && \
    chmod +x /usr/local/bin/nak

# Set up the working directory and virtual environment
WORKDIR /home/admin
RUN python -m venv sync_venv
COPY requirements.txt .
RUN sync_venv/bin/pip install -r requirements.txt

# Copy the application code
COPY . nostr-sync-scripts

# Create the crontab file
RUN echo '# Run grow_fedi_nhex every minute\n\
* * * * * . /home/admin/sync_venv/bin/activate && python /home/admin/nostr-sync-scripts/grow_fedi_nhex.py >> /var/log/cron.log 2>&1\n\
\n\
# Run fedi_sync every 2 minutes\n\
*/2 * * * * . /home/admin/sync_venv/bin/activate && python /home/admin/nostr-sync-scripts/fedi_sync.py >> /var/log/cron.log 2>&1\n\
\n\
# Run news_sync every 3 minutes\n\
*/3 * * * * . /home/admin/sync_venv/bin/activate && python /home/admin/nostr-sync-scripts/news_sync.py >> /var/log/cron.log 2>&1\n\
' > /etc/cron.d/nostr-sync

# Give execution rights to the crontab file
RUN chmod 0644 /etc/cron.d/nostr-sync

# Create log file and give appropriate permissions
RUN touch /var/log/cron.log && chmod 0666 /var/log/cron.log

# Install the crontab
RUN crontab /etc/cron.d/nostr-sync

# Create script to run cron and tail logs
RUN echo '#!/bin/bash\n\
echo "[$(date)] Starting cron service..." >> /var/log/cron.log\n\
service cron start\n\
tail -f /var/log/cron.log\n\
' > /home/admin/start.sh && chmod +x /home/admin/start.sh

# Start cron and tail the logs
CMD ["/home/admin/start.sh"]