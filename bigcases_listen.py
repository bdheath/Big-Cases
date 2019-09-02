# -*- coding: utf-8 -*-
"""

    ######     ######           ######  #######  ######   #
    #     #   #                #           #     #     #  #
    ######    #         #####  #           #     ######   #
    #     #   #                #           #     #   #    #
    ######     ######           ######     #     #    #   #######

	BIG CASES BOT CONTROL SCRIPT
	
	This script automates control of the @big_cases bot using Twitter mentions.
	
	Commands are accepted only from APPROVED users. Commands are:
	
		- follow [case name], No. [case number] in [court bluebook abbr.]. 
		  requires a literal case number and the precise court abbreviation
		  if successful, it will add the case to the roster and tweet an update
		  if not, it will reply with the reason
		  
		- Can you find the [party] case?
		  Find the most recent docket entry matching '%party%' and return the 
		  case number and title. Optionally, specify the court where the case can be
		  found with 'in [court abbr.]' Note that this only searches filings posted
		  within the past week. 
		  
		  Follow-ups are acceptable:
		  
		    - If it finds the case number, reply 'follow that one'
			  and the bot will add it to the list. If the reply also inclues
			  the phrase 'call it [alias].' you can specify an alias for the case.
			  For example, 'Follow that one. Call it Michael Cohen search warrant
			  case.'

		- Can you try that again?
		  Automatically try to re-up a document that didn't appear to download
		  correctly the last time. (Only works on the latest filing of this type
		  in this case, because tweets aren't associated with docket IDs.)
		  
		- What's your status?
		  Reply with the number of minutes since the last successful check for new
		  records and the last time a document was successfully uploaded. 
		  
		- When was the [court] feed last updated?
		  Get the elapsed time, in minutes, since a new filing was added for [court], 
		  or an error if the court isn't available. 
			  
		- If a non-approved users asks it to follow a case, reply with no.
		
		- Keep trying
		  If the bot can't find a case based on a name query, tell it to
		  'keep trying' and it will continue to look for hits in new filings

		- Thank @someone
		  Send a thank-you message to a particular recipient by saying
		  'thank @someone '. 

"""
	
import dbconnect
import json
import random
import requests
import re
#from __future__ import unicode_literals
from io import BytesIO
from twython import Twython
from pacer_rss_feeds import courts


# Approved users by Twitter screen name
APPROVED = ['bradheath', 'npenzenstadler', ]

# Lists of outgoing messages
#SAY SOMETHING TO UNAUTHORIZED USERS WHO GIVE A COMMAND
NOTAPPROVED = ['Who dares disturb my slumber?', 
				'... and you are?',
				'New phone, who dis?',  ]

# SAY YES				
CANDO = ['Can do.',
			'Yeah, sure, fine.',
			'You bet.', 
			'Why not.',
			'Yeah, OK.', 
			'Copy that.',
			'Yeah, whatever.',
			'Right away.',
			'Gladly.',
			'Yes, yessee yes yes yes.',
			'Affirmative.',
			'Yep.', 
			'I simply cannot wait to do that.',
			'Definitely.',
			'Roger wilco.', 
			'If you say so.', 
			'Yes sir, __sender__.',
			'OK ' + random.choice(['boss', 'chief', 'champ']) + '.',
			'http://gif.co/O2UO.gif',
			'You got it, ' + random.choice(['tiger', 'tough guy', 'champ', 'sport']) + '.',
			'I will try to do that right now, __sender__',
			'You\'re the boss, __sender__.',]

# FAMOUS
FAMOUS = ['http://gif.co/MpjV.gif', ]

# SAY NO
NOPE = ['Nope.',
		'Nah.',
		'Negative.',
		'Not gonna happen.',
		'Negatory',
		'http://gif.co/tGBj.gif',
		'http://gif.co/OgUX.gif',
		'http://gif.co/t3Hf.gif',
		'http://gif.co/uJzx.gif',
		'If only.',
		'In your dreams, __sender__.',
		'Yeah, no.',
		'Pffft.',
		'No way, __sender__.',
		'Make me.',
		'Keep dreaming, __sender__.',
		'I\'m sorry, __sender__, I\'m afraid I can\'t do that.',
		]

# SAY YOU'RE DOING SOMETHING DUMB
DUMB = ['Huh?',
		'That makes no sense, __sender__.',
		'I\'m confused.',
		'I am unlikely to fall for that.',
		'I have no idea what you\'re talking about, __sender__.', ]
	
GRUMBLE = ['Yeah, who built this thing anyway?',
			'<grumble grumble> stupid user',
			'These things happen, __sender__.',
			'http://gif.co/ohbE.gif',
			'I really don\'t think this is my fault, __sender__.', 
			'Not working the way you expected, __sender__? Wonder whose fault that could be.', ]
	
# SYNONYMS FOR DID YOU MEAN
DIDYOUMEAN = ['Are you talking about',
				'Did you mean',
				'Is that',
				'Are you thinking of',
				'This one?', ]

# SAY YOU'RE FOLLOWING SOMETHING
NOWFOLLOW = [ 'I\'m now following',
				'I just followed',
				'Now tracking',
				'This account will post updates from',
				'I\'ll post new documents from',
				'I\'ll post updates on', ]
				
# SAY YOU'RE WELCOME
WELCOME = [ 
			'http://gif.co/rjqD.gif', 
			'Sure, whatever.', 
			'Oh, definitely. I\'m happy to do all your work. That\'s totally fine.',
			'Lose my number.', 
			'#&%$.',
			'Sure.',
			'Not like I have anything else to do.',
			'Oh, yeah, that was really fun for me.',
			'You. Are. Welcome.',
			'http://gif.co/QlO8.gif',
#			'https://tenor.com/ytWA.gif',
#			'https://tenor.com/uS9d.gif',
			'I live for this stuff!', ]
			

GOTITRIGHT = ['I\'m pretty sure I got it right the first time.',
			'Why?', 
			'Why don\'t you do it instead?',
			'Do it yourself.', ]

THANKSOMEONE = [ 'http://gif.co/oYLP.gif',
					'http://gif.co/v1P7.gif', 
					'http://gif.co/20m1.gif',
					'Hey, thanks, __recipient__!', ]
	
# Regex control patterns	
FOLLOWPATTERN = re.compile('follow (.*?),? No. (.*?)\s{0,}(,|in|at) (.*?)[\?\,\!]{0,}$', re.IGNORECASE)
CLERKPATTERN = re.compile('go to the clerk', re.IGNORECASE)
FOLLOW = re.compile('^.{0,30} follow ', re.IGNORECASE)
FINDPATTERN = re.compile('find the (?:newest |latest :?)?(.*) case?', re.IGNORECASE)
FOLLOWTHAT = re.compile('follow that (one|case)', re.IGNORECASE)
CALLITPATTERN = re.compile('call it (.*?)\.$', re.IGNORECASE)
INPATTERN = re.compile('in (.*?)[\.\?\!]?$', re.IGNORECASE)
PRIORPATTERN = re.compile('(?:mean|about|thinking of|This one\?|Is that:?) (.*?), No. (.*?) in (.*?)\?', re.IGNORECASE)
THANKPATTERN = re.compile('(thank you|thanks|good robot|good bot)', re.IGNORECASE)
THANKSOMEONEPATTERN = re.compile('thank (@.*?) ', re.IGNORECASE)
MERCIPATTERN = re.compile(' merci.{0,10}$', re.IGNORECASE)
TRYAGAINPATTERN = re.compile('try (?:it :?)?(?:that :?)?(?:one :?)?again', re.IGNORECASE)
NEWFILINGPATTERN = re.compile('filing in (.*?): (.*?)\n', re.IGNORECASE)
NOTINFEEDPATTERN = re.compile('not in the feed', re.IGNORECASE)
FEEDCHECKPATTERNS = [
	re.compile('latest feed from (.*)\?', re.IGNORECASE),
	re.compile('the (.*?) feed (?:last :?)?updated', re.IGNORECASE),
]
STATUSPATTERN = re.compile('your (status|situation|20|condition)', re.IGNORECASE)
GRUMBLEPATTERN = re.compile('(grumble|stupid|argh|ugh|barf|bad bot|bad robot) ', re.IGNORECASE)
TITLECLEANPATTERN = re.compile('^(\d\:\d\d)-(cr|cv|mi|mc|ms|misc|sw)-([\d\-]{4,}) ', re.IGNORECASE)
FAMOUSPATTERN = re.compile('re famous', re.IGNORECASE)
TRYINGPATTERN = re.compile('(keep trying|keep at it|find it later|look for it later|keep looking)', re.IGNORECASE)

db = dbconnect.db()


case_file = open('bigcases.json')
case_data = json.load(case_file)
cases = case_data['cases']
cases_sct = case_data['supreme_court_cases']

# Do the formatting and stff on a list of message choices; return message and images
# Note that the recipient identifier should travel WITH THE @ SYMBOL ATTACHED
def postreply(l, sender, id = None, recipient = None):
	global tw
	images = []
	media_id = None
	reply = {} 
	print 'ok'
	# Pick one from the list
	m = random.choice(l).replace('__sender__', '@' + sender)
	
	if recipient is not None:
		m = m.replace('__recipient__', recipient)

	# Handle image replies; post media for embedding
	URLPATTERN = re.compile('^https*://', re.IGNORECASE)
	if URLPATTERN.search(m):
		res = requests.get(m)
		res.raise_for_status()
		uploadable = BytesIO(res.content)
		response = tw.upload_media(media=uploadable)
		media_id = response['media_id']
		if recipient is None:
			m = ' '
		else:
			m = recipient

		
	# Add sender ID
	msg = '@' + sender + ' ' + m
	reply['msg'] = msg
	reply['img'] = media_id
	
	if media_id is not None:
		media_ids = []
		media_ids.append(media_id)
		tw.update_status(status = msg, in_reply_to_status_id = id, media_ids = media_ids)
	else:
		tw.update_status(status = msg, in_reply_to_status_id = id)

	return

# Do the 'keep trying' queue
def keep_trying():
	global db
	global tw
	print '-> Checking the queue ...'
	
	r = db.getDict(""" SELECT *
						FROM court.bigcases_trying
						WHERE done = 0
						AND created >= DATE_ADD(NOW(), INTERVAL -72 HOUR)
						ORDER BY created DESC """)
	for l in r:
		print '   ... %s in %s (%s)' % (l['q'], l['court'], l['request_id'])
		if l['court'] is not None:
			court_where = ' AND court = \'' + l['court'] + '\''
		else:
			court_where = ''
	
		c = db.getDict(""" SELECT *
							FROM court.pacer_raw
							WHERE title LIKE %s
								AND modified >= DATE_ADD(NOW(), INTERVAL -1 HOUR)
								""" + court_where + """
							ORDER BY modified DESC
							LIMIT 1 """, ('%' + l['q'] + '%', ))
		
									
		if len(c) == 1:
						
			title = re.sub(TITLECLEANPATTERN, '', c[0]['title'])		
			msg = "@" + l['requested_by'] + " " + random.choice(DIDYOUMEAN) + " %s, No. %s in %s?" % (title, c[0]['case_number'], c[0]['court'] )
			tw.update_status(status = msg, in_reply_to_status_id = l['request_id'])
			
			db.run(""" UPDATE court.bigcases_trying
						SET done = 1
						WHERE request_id = %s """, (l['request_id'], ))


		
# Check whether this case is already on the list
def check_case(case_number, court, sender):
	for c in cases:
		if c['case_number'] == case_number and c['court'] == court:
			return '@%s Good news! I already follow %s, No. %s (%s)' % (sender, c['name'], c['case_number'], c['court'])
	return 'new'

# Check on availability of records for this court. Return either a sorry message, a data note or nothing.
def check_court(court, sender):
	ct = any(a['id'] == court for a in courts)
	if not ct:
		return '@%s Sorry, I don\'t have a good data feed for %s yet so I can\'t do that.' % (sender, court)
	else:
		for c in courts:
			if c['id'] == court:
				if 'data_note' in c:
					return '(%s)' % c['data_note']
				else:
					return ''
				break
				
	
if __name__ == '__main__':

	reply = False

	tw = Twython(
		'gbSMTxVXuEDhwaRALxP4xuUce',
		'yItP8Ix0j4JxXur9sTpuWetSR4syCtu0SlUKCgImWjJqb7DjUG',
		 '827523329527541761-ZV7G10HtjO9s8AhsO1hAyQYs9XtfYjy',
		 'LIuPTnQWDkFIdTIDzfoVHWMREOPIGokDNL3icQCoWinjY'
	)

	keep_trying()

	print '-> Checking the new mentions ...'
	
	mentions = tw.get_mentions_timeline(count = 100, tweet_mode = 'extended')
	
	for mention in mentions:
		
		if db.getOne(""" SELECT COUNT(*) 
					FROM court.bigcases_mentions
					WHERE id = %s """, (mention['id'], )) == 0:

			print '[tw-m]->%s %s' % (mention['id'], mention['full_text'][:50].encode('ascii','ignore'))

					
			# This is a mention we have not seen before

			message = mention['full_text']
			sender = mention['user']['screen_name']
			sender_id = mention['user']['id_str']
			
			db.run(""" REPLACE INTO court.bigcases_mentions(id, txt, screen_name, user_id, in_reply_to_status_id)
					VALUES(%s, %s, %s, %s, %s) """,
					(mention['id'], mention['full_text'].encode('ascii','ignore'), sender, sender_id, str(mention['id'])))
			
			
			# Check whether this is an approved requestor
			if sender.lower() in APPROVED:

				id = str(mention['id'])

				# Goof
				if CLERKPATTERN.search(message):
					msg = 'Sure. You just wait right there until I get back.'
					tw.update_status(status = '@' + sender + ' ' + msg, in_reply_to_status_id = id)
				
				if MERCIPATTERN.search(message):
					print 'merci'
					msg = u'รงa ne fait rien.'
					tw.update_status(status = '@' + sender + ' ' + msg, in_reply_to_status_id = id)
				
				# Check the bot's status
				if STATUSPATTERN.search(message):
					id = str(mention['id'])
					last_doc = db.getDict("""  SELECT DATE_FORMAT(modified, '%%W at %%h:%%i %%p') AS dt,
												MINUTE(TIMEDIFF(modified, NOW())) AS m
											  FROM court.bigcases_status
											  WHERE k = 'last-docs'; """)[0]

					last_scrape = db.getDict("""  SELECT DATE_FORMAT(modified, '%%W at %%h:%%i %%p') AS dt,
												MINUTE(TIMEDIFF(modified, NOW())) AS m
											  FROM court.bigcases_status
											  WHERE k = 'last-feed'; """)[0]
								
					if last_scrape['m'] == 0:
						m = 'less than a minute'
					elif last_scrape['m'] == 1:
						m = 'a minute'
					else:
						m = str(last_scrape['m']) + ' minutes'
						
					msg = '@' + sender + ' I checked for new court filings ' + m + ' ago. The last time I scraped a district court document was ' + last_doc['dt'].replace('AM','a.m.').replace('PM','p.m.')
					tw.update_status(status = msg, in_reply_to_status_id = id)
					
				# Get the latest feed update
				for p in FEEDCHECKPATTERNS:
					m = p.search(message)
					if m:
						court = m.group(1)
						court_msg = check_court(court, sender)						
						if 'Sorry' in court_msg:
							# If we don't follow that court, say so
							tw.update_status(status = '@' + sender + ' ' + court_msg, in_reply_to_status_id = str(mention['id']))
						else:
							r = db.getOne(""" SELECT MINUTE(TIMEDIFF(t.modified, NOW())) AS m
								FROM (
								SELECT modified
								FROM court.pacer_raw
								WHERE court = %s
								order by modified desc
								limit 1
								) AS t """, (court, ))
							LATEST = ['Looks like the latest item in the __court__ feed was from __minutes__ minutes ago.',
									'I found something from __court__ __minutes__ minutes ago.' ]
							l = random.choice(LATEST)
							l = l.replace('__court__',court)
							l = l.replace('__minutes__', str(r))
							msg = '@' + sender + ' ' + l
							tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
						break
			
				# Find if we have a case
				m = FINDPATTERN.search(message)
				if m:
					court_where = ''
					if INPATTERN.search(message):
						court_where = " AND court = '" + INPATTERN.search(message).group(1) + "' "
					
					c = db.getDict(""" SELECT *
									FROM court.pacer_raw
									WHERE title LIKE %s
										AND modified >= DATE_ADD(NOW(), INTERVAL -21  DAY)
										""" + court_where + """
									ORDER BY modified DESC
									LIMIT 1 """, ('%' + m.group(1) + '%', ))
									
					if len(c) == 0:
						
						msg = "@" + sender + " " + random.choice(NOPE).replace('__sender__', '@' + sender)
						postreply(NOPE, sender, id = str(mention['id']))
						
					else:
						
						title = re.sub(TITLECLEANPATTERN, '', c[0]['title'])
					
						msg = "@" + sender + " " + random.choice(DIDYOUMEAN) + " %s, No. %s in %s?" % (title, c[0]['case_number'], c[0]['court'] )
						
						tw.update_status(status = msg, in_reply_to_status_id = mention['id'])
			
				m = FOLLOWTHAT.search(message)
				if m and mention['in_reply_to_status_id'] is not None:
#					print '### FOLLOW THAT ###'
					prior_id = mention['in_reply_to_status_id']
					prior = tw.show_status(id = prior_id, tweet_mode='extended')
					
					m = PRIORPATTERN.search(prior['full_text'])
					if m:
#						print 'Prior: %s' % m.group(2)
						name = re.sub(TITLECLEANPATTERN, '', m.group(1))
						# If you've asked the case to have a particular name
						cpm = CALLITPATTERN.search(message)
						if cpm:
							name = cpm.group(1)
						
						case_number = m.group(2)
						court = m.group(3)
					
						new = check_case(case_number, court, sender)
						if new == 'new':

							# Add this to the list and update the file
							cases.append({'name':name, 'case_number': case_number, 'court':court })
							out = { 'supreme_court_cases': cases_sct, 'cases':cases }
							with open('bigcases.json','w') as listfile:
								listfile.write(json.dumps(out, indent=4))

							filings = db.getDict(""" UPDATE court.pacer_raw
													SET bigcase = 1
													WHERE bigcase = 0
														AND case_number = %s
														AND court = %s
														AND modified >= DATE_ADD(NOW(), INTERVAL -48 HOUR)
													ORDER BY modified DESC
													LIMIT 10 """, (case_number, court, ))
							
							msg = '@' + sender + ' ' + CANDO[random.randint(0, len(CANDO) -1)].replace('__sender__', '@' + sender)
							tw.update_status(status=msg, in_reply_to_status_id = str(mention['id']))
													
							# Tell us you have added it. Include any data notes for that court?
							msg = random.choice(NOWFOLLOW)+ ' %s, No. %s in %s. %s' % (name, case_number, court, check_court(court, sender))
						
							tw.update_status(status = msg)
			
						else:
							# Oops, we already have this one
							msg = new
							tw.update_status(status = new, in_reply_to_status_id = str(mention['id']))

				elif GRUMBLEPATTERN.search(message):
					prior_id = mention['in_reply_to_status_id']
					prior = tw.show_status(id = prior_id, tweet_mode='extended')
					
					# Only reply to responses to bot messages
					if prior['user']['screen_name'] == 'big_cases':
						msg = '@' + sender + ' ' + random.choice(GRUMBLE).replace('__sender__','@' + sender)
						tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
							
				elif FAMOUSPATTERN.search(message):
				
					postreply(FAMOUS, sender, id = str(mention['id']))
				
				elif THANKSOMEONEPATTERN.search(message):
					
					recipient = THANKSOMEONEPATTERN.search(message).group(1)
					postreply( THANKSOMEONE, sender, id = str(mention['id']), recipient = recipient)
				
				elif THANKPATTERN.search(message) and mention['in_reply_to_status_id'] is not None:
				
					msg = '@' + sender + ' ' + random.choice(WELCOME)
					postreply(WELCOME, sender, id = str(mention['id']))
					#tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))

				elif THANKPATTERN.search(message):
					postreply(WELCOME, sender, id = str(mention['id']))

				elif TRYAGAINPATTERN.search(message) and mention['in_reply_to_status_id'] is not None:
					# This is asking me to try an upload again
					print 'trying that again'					
					# First, get the previous status to figure out what to try again
					prior_id = mention['in_reply_to_status_id']
					prior = tw.show_status(id = prior_id)
					
					
					# Then, see if it needs updating (does it have a DC link?)
					has_doc = False
					for u in prior['entities']['urls']:
						if 'documentcloud' in u['display_url']:
							has_doc = True
							break
							
					if has_doc:
						msg = '@' + sender + ' ' + random.choice(GOTITRIGHT)
						tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
					else:
						# Then, figure out what this was
						if NEWFILINGPATTERN.search(prior['text']):
							name = NEWFILINGPATTERN.search(prior['text']).group(1)
							desc = NEWFILINGPATTERN.search(prior['text']).group(2)
							
							# Figure out what case number goes with this
							cur_case = None
							for c in cases:
								if c['name'] == name:
									cur_case = c
									break
							
							# Now, look for records of this in the db
							pid = db.getOne(""" SELECT pid
											FROM court.pacer_raw
											WHERE court = %s
												AND case_number = %s
												AND description LIKE %s
											ORDER BY pid DESC
											LIMIT 1 """, 
											( c['court'], c['case_number'],
											'%' + desc + '%', ))
							if pid:
								# Mark it to try again
								db.run(""" UPDATE court.pacer_raw
											SET bigcase = 1
											WHERE pid = %s """,
											(pid, ))
								
								# Say yes
								msg = '@' + sender + ' ' + random.choice(CANDO).replace('__sender__', '@' + sender)
								tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
							else:
								# It didn't work; say no
								msg = '@' + sender + ' ' + random.choice(NOPE).replace('__sender__','@' + sender)
								tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
								
						
						else:
							# You're trying to do something dumb
							msg = '@' + sender + ' ' + random.choice(DUMB).replace('__sender__','@'+sender)
							tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
							
				# Keep trying
				m = TRYINGPATTERN.search(mention['full_text']);
				if m:
					# Go back and find the search terms
					prior_id = mention['in_reply_to_status_id']
					i_prior_id = prior_id
					prior = tw.show_status(id = prior_id, tweet_mode='extended')					
					prior_id = prior['in_reply_to_status_id']
					prior = tw.show_status(id = prior_id, tweet_mode='extended')					
					
					
					# Add it to the queue
					p = FINDPATTERN.search(prior['full_text'])
					if p:
						q = p.group(1)
						c = ''
						i = INPATTERN.search(prior['full_text'])
						if i:
							c = i.group(1)
						print 'q = %s ' % q
						print 'c = %s ' % c
						
						db.run(""" REPLACE INTO court.bigcases_trying(requested_by, request_id, q, court, created)
									VALUES(%s, %s, %s, %s, NOW()) """,
									(prior['user']['screen_name'], mention['id'], q, c, ))
						postreply(CANDO, sender, str(mention['id'])) 
			
				# Check whether this is a valid request
				m = FOLLOWPATTERN.search(mention['full_text'])
				if m:
					print 'Got your message'
					print 'New case: %s, No. %s in %s' % (m.group(1), m.group(2), m.group(4))
					case_number = m.group(2)
					court = m.group(4)
					name = m.group(1)

					# First, see if we already have it
					new = check_case(case_number, court, sender)
					if new == 'new':
						# Next, check to see if we have that court
						court_msg = check_court(court, sender)
						if 'Sorry' in court_msg:
							msg = court_msg
							reply = True
						else:
							# Next, check to see if it's in the db
							proc = False
							if NOTINFEEDPATTERN.search(message):
								# Continue without checking the db
								proc = True
							else:
								if db.getOne(""" SELECT COUNT(*) AS c
											FROM court.pacer_raw
											WHERE case_number = %s
												AND court = %s """, (case_number, court, )) == 0:
									reply = True
									msg = '@%s That case isn\'t in my database.' % sender
									proc = False
								else:
									proc = True
							if proc:
						
						
								# Add this to the list and update the file
								cases.append({'name':name, 'case_number': case_number, 'court':court })
								out = { 'supreme_court_cases': cases_sct, 'cases':cases }
								with open('bigcases.json','w') as listfile:
									listfile.write(json.dumps(out, indent=4))
								
								# Go back and update some filings from today

								filings = db.getDict(""" UPDATE court.pacer_raw
													SET bigcase = 1
													WHERE bigcase = 0
														AND case_number = %s
														AND court = %s
														AND modified >= DATE_ADD(NOW(), INTERVAL -24 HOUR)
													ORDER BY modified DESC
													LIMIT 10 """, (case_number, court, ))

								# confirm
								msg = '@' + sender + ' ' + CANDO[random.randint(0, len(CANDO) -1)].replace('__sender__', '@' + sender)
								tw.update_status(status=msg, in_reply_to_status_id = str(mention['id']))
													
								# Tell us you have added it. Include any data notes for that court?
								msg = 'I\'m now following %s, No. %s in %s. %s' % (name, case_number, court, check_court(court, sender))
						
					else:
						msg = new
						reply = True
						
					# Now post the message
					print 'RESULT: %s' % msg
					if reply:
						tw.update_status(status = msg, in_reply_to_status_id = str(mention['id']))
					else:
						tw.update_status(status = msg)
		
			else: 
				# Not approved sender
				if mention['in_reply_to_status_id'] is None:
					if FOLLOW.search(message) or FINDPATTERN.search(message):
						print ' - Somebody has disturbed my slumbe'
						msg = NOTAPPROVED[random.randint(0, len(NOTAPPROVED) -1)].replace('__sender__','@' + sender)
						id = str(mention['id'])
						tw.update_status(status = '@' + sender + ' ' + msg, in_reply_to_status_id = id)

