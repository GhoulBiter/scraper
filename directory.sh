# Create the directory structure
mkdir -p ./{utils,crawler,analysis,database,models,output}

# Create __init__.py files in all directories
touch ./__init__.py
touch ./utils/__init__.py
touch ./crawler/__init__.py
touch ./analysis/__init__.py
touch ./database/__init__.py
touch ./models/__init__.py
touch ./output/__init__.py

# Create main files
touch ./main.py
touch ./config.py

# Create utility module files
touch ./utils/logging_config.py
touch ./utils/encoding.py
touch ./utils/url_utils.py

# Create crawler module files
touch ./crawler/queue.py
touch ./crawler/worker.py
touch ./crawler/fetcher.py
touch ./crawler/shutdown.py
touch ./crawler/monitor.py

# Create analysis module files
touch ./analysis/link_extractor.py
touch ./analysis/page_analyzer.py
touch ./analysis/ai_evaluator.py

# Create database module files
touch ./database/db_operations.py
touch ./database/metrics_storage.py

# Create model module files
touch ./models/application_page.py
touch ./models/crawl_stats.py

# Create output module files
touch ./output/exporter.py

echo "Project structure created successfully!"