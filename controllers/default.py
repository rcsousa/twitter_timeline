# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a sample controller
## - index is the default action of any application
## - user is required for authentication and authorization
## - download is for downloading files uploaded in the db (does streaming)
## - api is an example of Hypermedia API support and access control
#########################################################################

def index():
    """
    example action using the internationalization operator T and flash
    rendered by views/default/index.html or views/generic.html

    if you need a simple wiki simply replace the two lines below with:
    return auth.wiki()
    """

    return dict()

@auth.requires_login()
def post():
    from tweet_tasks import save_post, update_timeline, populate_cloudant, populate_index
    import uuid
    form=SQLFORM(db.tweet,fields=['post'],formstyle='bootstrap')
    form.vars.tweet_id = uuid.uuid1()
    form.vars.user_id=auth.user_id
    form.vars.created_on=request.now
    if form.validate(): # vai ser o insert
        #response.flash=form.vars.created_on
        save_post.delay(form.vars.tweet_id,form.vars.user_id,form.vars.post,form.vars.created_on)
        update_timeline.apply_async((form.vars.tweet_id,form.vars.user_id,form.vars.created_on),countdown=3)
        populate_index.apply_async((form.vars.user_id,form.vars.post,form.vars.created_on),countdown=5)
        populate_cloudant.apply_async((form.vars.user_id,form.vars.post,form.vars.created_on),countdown=7)

    return dict(form=form)

@auth.requires_login()
def timeline():
    try:
        import memcache, redis, requests, traceback
        from tweet_tasks import recreate_timeline, recreate_memcache
        url  = "http://twitkiller-mc.mybluemix.net/cache/"
        rd=redis.Redis('localhost')
        #mc = memcache.Client(['localhost:11211'], debug=1)
        posts=rd.lrange('%s' %auth.user_id, '0', '30')
        if posts:
            cached_posts = []
            post_uid = []
            post_created_on = []
            for p in posts:
                cp = requests.get(url+'%s' %p.split(';')[0])
                #cp = mc.get('%s' %p.split(';')[0])
                if cp.status_code != 200:
                    result = recreate_memcache.delay(auth.user_id)
                    list = result.get()
                    return dict(list=list)
                else:
                    #cached_posts.append(mc.get('%s' %p.split(';')[0]))
                    get_cache = requests.get(url+'%s' %p.split(';')[0])
                    cache_content = get_cache.text
                    #cached_posts.append(requests.get(url+'%s' %p.split(';')[0]))
                    cached_posts.append(cache_content)
                    post_uid.append(p.split(';')[1])
                    post_created_on.append(p.split(';')[2])
            return dict(cached_posts=zip(cached_posts,post_uid,post_created_on))
        else:
            cached_posts = []
            post_uid = []
            post_created_on = []
            result = recreate_timeline.delay(auth.user_id)
            posts = result.get()
            for p in posts:
                get_cache = requests.get(url+'%s' %p.split(';')[0])
                cache_content = get_cache.text
                cached_posts.append(cache_content)
                #cached_posts.append(mc.get('%s' %p.split(';')[0]))
                post_uid.append(p.split(';')[1])
                post_created_on.append(p.split(';')[2])
            return dict(cached_posts=zip(cached_posts,post_uid,post_created_on))
    except:
        list = "Oops !! It seems that our Redis cluster is down. But fear nothing, a team of trained monkeys were dispatched to fix it !!!"
        #return dict(list=list)
        return traceback.format_exc()

@auth.requires_login()
def search():
    import urllib2, traceback
    from tweet_tasks import search_tweet
    if request.vars['q']:
        try:
            list = []
            query = urllib2.quote(request.vars['q'])
            result = search_tweet.apply_async((query,),  queue='search')
            list = result.get()
            return list
        except:
            return traceback.format_exc()
    else:
        query=[]
        list = dict(post=query)
        return list


@auth.requires_login()
def user_directory():
    import memcache
    users=db(db.auth_user.id!=auth.user_id).select()
    mc = memcache.Client(['localhost:11211'], debug=1)
    following=mc.get('following_%s' %auth.user_id)
    if not following:
        following=[f.following for f in db(db.follow.follower==auth.user_id).select(db.follow.following)]
        mc.set('following_%s' %auth.user_id, following)
    return dict(users=users,following=following)

@auth.requires_login()
def follow():
    from tweet_tasks import do_follow
    user_id=request.args(0)
    do_follow.delay(int(auth.user_id),int(user_id))
    return

@auth.requires_login()
def unfollow():
    from tweet_tasks import do_unfollow
    user_id=request.args(0)
    do_unfollow.delay(int(auth.user_id),int(user_id))
    return

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    http://..../[app]/default/user/manage_users (requires membership in
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())


@cache.action()
def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request, db)


def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()


@auth.requires_login() 
def api():
    """
    this is example of API with access control
    WEB2PY provides Hypermedia API (Collection+JSON) Experimental
    """
    from gluon.contrib.hypermedia import Collection
    rules = {
        '<tablename>': {'GET':{},'POST':{},'PUT':{},'DELETE':{}},
        }
    return Collection(db).process(request,response,rules)
