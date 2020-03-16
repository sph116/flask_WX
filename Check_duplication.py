import redis

class Operation_Redis():

    """
    redis 数据库连接池 及增删改查
    """

    def __init__(self):
        self.host = ""
        self.psw = ""
        self.port = 6379
        self.db = 6
        self.pool = redis.ConnectionPool(host=self.host, password=self.psw, port=self.port, db=self.db, max_connections=50)

    def check_duplication(self, username_time):
        """
        检测键值是否存在于redis 若存在 若存在返回空字符串 不存在则插入
        :param username_time:
        :return:
        """
        r = redis.Redis(connection_pool=self.pool, decode_responses=True)
        flag = r.exists(username_time, '')    # 判断键值是否存在   hexists
        if flag == 0:
            r.set(username_time, '', ex=86400)  # 存储
            return 1
        elif flag == 1:
            return ''


    def save_uesr_rec(self, user_id, type='', rec=''):
        """
        判断用户上一次停留位置
        用户查看问题后 将位置存储mysql 超过五分钟删除
        下次查看 若大于5分钟 则返回重新浏览
        小于 则进入上次停留位置
        :param user_id:
        :param rec:
        :return:
        """
        r = redis.Redis(connection_pool=self.pool, decode_responses=True)
        flag = r.exists(user_id)  # 判断键是否存在   # hexists
        if flag == 1:
            rec = r.get(user_id)
            r.delete(user_id)
            if type != "":
                r.set(user_id, rec, ex=300)

            return rec
        else:
            if type != "":
                r.set(user_id, rec, ex=300)
            return False

Redis = Operation_Redis()
