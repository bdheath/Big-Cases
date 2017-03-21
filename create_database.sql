CREATE DATABASE IF NOT EXISTS court
;

CREATE TABLE IF NOT EXISTS court.pacer_raw (
	pid INT(11) NOT NULL AUTO_INCREMENT,
	court VARCHAR(255) NULL DEFAULT NULL,
	case_number VARCHAR(255) NULL DEFAULT NULL,
	title VARCHAR(255) NULL DEFAULT NULL,
	guid VARCHAR(255) NULL DEFAULT NULL,
	modified DATETIME NULL DEFAULT NULL,
	pubdate VARCHAR(255) NULL DEFAULT NULL,
	description TEXT NULL,
	link VARCHAR(255) NULL DEFAULT NULL,
	scraped INT(11) NULL DEFAULT '0',
	scraped_time DATETIME NULL DEFAULT NULL,
	dcid VARCHAR(50) NULL DEFAULT NULL,
	document_location VARCHAR(255) NULL DEFAULT NULL,
	price DOUBLE NULL DEFAULT NULL,
	preflag INT(11) NULL DEFAULT '0',
	bigcase INT(11) NULL DEFAULT '0',
	PRIMARY KEY (pid),
	INDEX case_number_idx (case_number),
	INDEX title_idx (title),
	INDEX modified_idx (modified),
	INDEX court_idx (court),
	INDEX court_case_number_idx (court, case_number),
	INDEX guid_idx (guid),
	INDEX scraped_idx (scraped),
	INDEX price_idx (price),
	INDEX preflag_idx (preflag),
	INDEX bigcase_idx (bigcase),
	FULLTEXT INDEX description_ftidx (description)
) ENGINE=MyISAM, CHARSET=UTF8
;
