
class settings:

	# Scrape settings
	multitask = False					# Use multiprocessing for scraping RSS?
	multitask_threads = 5
	http_timeout = 30.0					# How long to wait for http requests
	file_temp_path = ''					# Set a temporary path for working with PDFs (i.e., /data/pacer)
	file_archive_path = ''				# Set a folder to archive downloaded PDFs (i.e., /data/pacer/archive)
	max_files_to_scrape = 10

	# Database settings (MySQL server)
	db_host = ''						# MySQL host name
	db_user = ''						# MySQL username
	db_pass = ''						# MySQL password
	db_port = 3306						# MySQL port

	# PACER settings
	pacer_user = ''					# PACER username
	pacer_pass = ''					# PACER password
	pacer_client = ''					# PACER client code
	pacer_max_price = 3.00				# Maximum amount to pay for PACER record
	
	# DocumentCloud credentials
	dc_user = ''						# DocumentCloud username
	dc_pass = ''						# DocumentCloud password
	dc_project_id = ''					# Numeric ID of DocumentCloud project to which to post
	
	# Twitter credentials
	twitter_app_key = ''
	twitter_app_secret = ''
	twitter_oauth_key = ''
	twitter_oauth_secret = ''

        # RECAP credentials
        recap_token=''
