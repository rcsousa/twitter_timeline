from celery import Celery
import json, os, pydal
import datetime
from pydal import DAL, Field
import memcache

config = {
  'user': 'tweet',
  'password': 'tweet',
  'host': '127.0.0.1',
  'database': 'tweet',
  'raise_on_warnings': True,
}

celery = Celery('tasks', backend='amqp', broker='amqp://localhost', task_result_expires='120')
#celery = Celery('tasks', backend='amqp', broker='amqp://guest:guest@localhost', task_result_expires='120')
db = DAL('mysql://tweet:tweet@localhost/tweet',folder=os.getcwd()+'/applications/twitkiller/databases',auto_import=True)

url  = "http://twitkiller-mc.mybluemix.net/cache/"

@celery.task(ignore_result=True, ALWAYS_EAGER=False)
def update_timeline(tweet_id,user_id,tweet_created_on):
    import redis
    rd=redis.Redis('localhost')
    user_rows = db(db.auth_user.id==user_id).select()
    for user_row in user_rows:
	user_name=user_row.first_name
    tweet_rows = db(db.tweet.tweet_id==tweet_id).select()
    #for t in tweet_rows:
	#tweet_created_on=t.created_on
    rows = db(db.follow.following==user_id).select()
    mytimeline_redis=rd.lpush('%s' %user_id, '%s;%s;%s' %(tweet_id,user_name,tweet_created_on))
    mytimeline_db=db.timeline.insert(tweet_guid=tweet_id,userid=user_id,tweeter=user_id,created_on=tweet_created_on)
    db.commit()
    for row in rows:
	timeline_redis=rd.lpush('%s' %row.follower, '%s;%s;%s' %(tweet_id,user_name,tweet_created_on))
	timeline_db=db.timeline.insert(tweet_guid=tweet_id,userid=row.follower,tweeter=user_id,created_on=tweet_created_on)
	db.commit()
    return timeline_redis 

@celery.task
def recreate_timeline(user_id):
    import redis
    rd=redis.Redis('localhost')
    #check = rd.exists(user_id)
    check='1'
    if check:
    	timeline=db(db.timeline.userid==user_id).select()
    	for row in timeline:
		user_rows = db(db.auth_user.id==row.tweeter).select()
		for user_row in user_rows:	
			timeline_redis=rd.lpush('%s' %user_id, '%s;%s;%s' %(row.tweet_guid,user_row.first_name,row.created_on))
    	posts=rd.lrange('%s' %user_id, '0', '-1')
    	return posts
    else:
	return "Oops !! It seems that our Redis cluster is down. But fear nothing, a team of trained monkeys were dispatched to fix it !!!"

@celery.task()
def recreate_memcache(user_id):
    import json, traceback
    from tw_functions import add_to_cache_bluemix
    try:
    	tweets = db(db.tweet).select()
    	for row in tweets:  
		args = { 'data' : '%s' %row.post }
		data = json.dumps(args)
		out = add_to_cache_bluemix(url+row.tweet_id, data)
	if out.status == 404:
		return "Oops !! It seems that our memcached cluster is down. But fear nothing, a team of trained monkeys was dispatched to fix it !!!"
	else:
		return out
    except:
    	return "Oops !! It seems that our memcached cluster is down. But fear nothing, a team of trained monkeys was dispatched to fix it !!!"
	#return traceback.format_exc()


@celery.task(ignore_result=True)
def save_post(tweet_id,user_id,post,created_on):
    import requests
    from tw_functions import add_to_cache_bluemix
    post_id=db.tweet.insert(tweet_id=tweet_id,user_id=user_id,post=post,created_on=created_on)
    db.commit()
    #mc = memcache.Client(['localhost:11211'], debug=1)
    #mc.set('%s' %tweet_id, post)
    args = { 'data' : '%s' %post }
    data = json.dumps(args) 
    out = add_to_cache_bluemix(url+str(tweet_id), data)
#    requests.put(url+str(tweet_id), data=data)
    return out

@celery.task(ignore_result=True, ALWAYS_EAGER=False)
def populate_index(user_id,post,created_on):
        from tw_functions import add_to_elasticsearch 
	import traceback
        try:
		user_rows = db(db.auth_user.id==user_id).select()
                for user_row in user_rows:
                        user_name=user_row.first_name
			post = post
 			created_on =created_on
		result = add_to_elasticsearch(user_name,post,created_on)
                print "Updated Tweet Index %s" % doc
		return result
        except:
                return traceback.format_exc()

@celery.task(ignore_result=True, ALWAYS_EAGER=False)
def populate_cloudant(user_id,post,created_on):
	import cloudant,hashlib,traceback,os
        try:   
		key = hashlib.sha1(post)
		key_hash = key.hexdigest()
		USERNAME = os.getenv('cloudant_username')
		PASSWORD = os.getenv('cloudant_password')
		account = cloudant.Account(USERNAME)
		login = account.login(USERNAME, PASSWORD)
		coudantdb = account.database('twitkiller')
		doc = coudantdb.document(key_hash)
                user_rows = db(db.auth_user.id==user_id).select()
                for user_row in user_rows:
                        user_name=user_row.first_name
                body = {
                        '_id': '%s' % key_hash,
                        'user_id': '%s' % user_name,
                        'post': '%s' % post,
                        'created_on': '%s' % created_on
			}
		print body
		resp = doc.put(params=body)
		print resp.json()
        except:
                #print "WTF"
		print traceback.format_exc()


@celery.task
def search_tweet(query, **kwargs):
    import urllib2, json 
    endpoint="https://rcsousa.cloudant.com/twitkiller/_design/view/_search/search?q="
    print query
    print kwargs
    print endpoint+str(query)
    request = endpoint+str(query)
    output = urllib2.urlopen(request)
    data = json.loads(output.read())
    print data
    id = []
    post = []
    user_id = []
    created_on = []
    for v in data['rows']:
	id.append(v['id'])
    for a in id:
	print a
	req = "https://rcsousa.cloudant.com/twitkiller/"+str(a)
	print req
	out = urllib2.urlopen(req)
	data1 = json.loads(out.read())
	print data1
	post.append(data1['post'])
	user_id.append(data1['user_id'])
	created_on.append(data1['created_on'])
    list = dict(post=tuple(post),user_id=tuple(user_id),created_on=tuple(created_on))
    return list


#@celery.task
#def search_tweet(query, **kwargs):
#    from elasticsearch import Elasticsearch
#    import urllib2, json
#    endpoint="http://localhost:9200/_search?q="
#    print query
#    print kwargs
#    print endpoint+str(query)
#    request = endpoint+str(query)
#    output = urllib2.urlopen(request)
#    data = json.loads(output.read())
#    print data
#    post = [] 
#    user_id = [] 
#    created_on = []
#    for v in data['hits']['hits']:
#        post.append(v['_source']['post'])
#        user_id.append(v['_source']['user_id'])
#        created_on.append(v['_source']['created_on'])
#    list = dict(post=tuple(post),user_id=tuple(user_id),created_on=tuple(created_on))
#    return list


@celery.task(ignore_result=True)
def do_follow(follower,following):
    if follower != following:
        f_id=db.follow.update_or_insert(follower=follower,following=following)
        db.commit()
        return f_id
    else:
        return 'nope!'

@celery.task(ignore_result=True)
def do_unfollow(follower,following):
    if follower != following:
        f_id=db((db.follow.follower==follower)&(db.follow.following==following)).delete()
        db.commit()
        return f_id
    else:
        return 'nope!'
