def add_to_cache_bluemix(url,data):
    import requests,traceback
    try:
        result = requests.put(url, data=data)
        return result 
    except:
	return traceback.format_exc()

def add_to_elasticsearch(user_name,post,created_on):
        from elasticsearch import Elasticsearch
	import traceback
        try:
                doc = {
                        'user_id': '%s' % user_name,
                       'post': '%s' % post,
                       'created_on': '%s' % created_on
                }
                es = Elasticsearch()
                result = es.index(index="tweet", doc_type="string", body=doc)
		return result
        except:
		return traceback.format_exc()


#def recreate_memcache(user_id):
#    try:
#        import memcache, urllib2, json, urllib, requests, traceback
#        from tw_functions import add_to_cache_bluemix
#        #mc = memcache.Client(['localhost:11211'], debug=1)
#        tweets = db(db.tweet).select()
#        for row in tweets:
#                args = { 'data' : '%s' %row.post }
#                data = json.dumps(args)
#                #print '%s' %row.tweet_id
#                #print args
#                #print data
#                #data = urllib.urlencode(args)
#                #request = urllib2.Request(url+row.tweet_id, data, {'Content-Type': 'application/json'})
#                out = add_to_cache_bluemix(url+row.tweet_id, data)
#                #return traceback.format_exc()
#                #posts = mc.set('%s' %row.tweet_id, '%s' %row.post)
#                #return traceback.format_exc()
#        #return "Oops !! It seems that our memcached cluster is down. But fear nothing, a team of trained monkeys were dispatched to fix it !!!"
#        return out
#    except:
#        #return "Oops !! It seems that our memcached cluster is down. But fear nothing, a team of trained monkeys were dispatched to fix it !!!"
#        return traceback.format_exc()
