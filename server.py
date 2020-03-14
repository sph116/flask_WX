from gevent import monkey; monkey.patch_all()
import difflib
from gevent import pywsgi
from flask import Flask
from flask import request, jsonify
from wechatpy.utils import check_signature
from wechatpy.exceptions import InvalidSignatureException
from wechatpy.replies import TextReply, ArticlesReply
from wechatpy import parse_message
from Check_duplication import Redis
import pandas as pd
import re


app = Flask(__name__)


def Reply_text(msg, reply_text):
    """
    用于回复文本数据
    :param msg:
    :param reply_text:
    :return:
    """
    reply_data = TextReply(content=reply_text, message=msg)
    reply_xml = reply_data.render()
    return reply_xml

def Reply_Article(msg, reply_dic):
    reply = ArticlesReply(message=msg)
    # simply use dict as article
    reply.add_article(reply_dic)
    return reply.render()


def extract_que(que_path):
    """
    提取所有问题回复数据
    返回问题分级字典 和答案字典
    :param que_path:
    :return:
    """
    que_df = pd.read_excel(que_path)

    que_dict = {}  # 序号对应问题字典
    ans_dict = {}  # 问题对应答案字典
    for column in que_df:
        que_dict[column] = {}

        for que in list(que_df[column]):
            if type(que) == str:
                que = que.replace("\n", "")

                if "  " in que:
                    ques = que.split("答案:")[0]
                    ques = ques.replace(re.search("(\d+(\.\d+)?)", ques).group(), '').strip()
                    ans = que.split("答案:")[1]
                    ans_dict[ques] = ans.strip()

                else:
                    que_index = que.split(".")[0]
                    if len(que_index) == 2:
                        que = que[3:]
                    else:
                        que = que[2:]

                    que_dict[column][que_index] = {}

                    # que_dict[column][que_index][que] = {j[2: 5]: j.split('\n')[0][5:] for j in list(que_df[column]) if "  " in j and que_index+"." in j}
                    que_dict[column][que_index][que] = {}

                    ls = list(que_df[column])

                    # if que_index == "3":
                    #     pass
                    for j in ls:
                        if type(j) == str:
                            if "  " in j and que_index + "." in j:
                                j = j.strip()
                                if re.search("(\d+(\.\d+)?)", j).group().split('.')[0] != que_index:
                                    pass
                                else:
                                    if len(que_index) == 2:
                                        que_dict[column][que_index][que][j[0: 4]] = j.split('\n')[0][4:]
                                    else:
                                        que_dict[column][que_index][que][j[0: 3]] = j.split('\n')[0][3:]

    return que_dict, ans_dict

@app.route('/check_token', methods=['GET'])
def Check_token():
    """
    用来验证微信公众号后台链接
    :return:
    """
    rq_dict = request.args
    if len(rq_dict) == 0:
        return ""
    signature = request.args.get('signature')   # 提取请求参数
    timestamp = request.args.get('timestamp')
    nonce = request.args.get('nonce')
    echostr = request.args.get('echostr')
    try:
        check_signature(token='jxgj8888', signature=signature, timestamp=timestamp, nonce=nonce)  # 使用wechat库验证
    except InvalidSignatureException as e:
        print(e)
        return ''
    else:
        print(111111)
        return echostr  # 返回数据




@app.route('/check_token', methods=['POST'])
def Reply_user():
    """
    用于自动回复客服消息
    :return:
    """

    que_dict, ans_dict = extract_que('./data/hk_ques_data（APRIL_20200226).xlsx')   # 加载问题及回复信息
    req_key_word = que_dict.keys()                                                  # 所有可回复的关键词

    wechat_send_data = request.data                           # 接收消息提醒 为xml格式
    msg = parse_message(wechat_send_data)                     # wechat模块解析数据
    FromUserName = msg.source           # 消息的发送用户
    CreateTime = msg.create_time        # 消息的创建时间
    ToUserName = msg.target             # 消息的目标用户


    duplication_flag = Redis.check_duplication("{}{}".format(FromUserName, CreateTime))  # 消息查重
    if duplication_flag == 1:
        pass
    else:
        print("推送重复")
        return ''   # 若重复 返回1

    if msg.type == "event":               # 为事件消息
        if msg.event == "subscribe":      # 关注事件回复
            return Reply_text(msg, '====自动回复=====\n   欢迎关注, 回复 {} 即可获取相关信息。').format("、".join(req_key_word))
        elif msg.event == "unsubscribe":  # 取关事件回复
            return Reply_text(msg, "====自动回复=====\n  下次再见。")
        elif msg.event == "click" and msg.key == "zhinengkefu":
            return Reply_text(msg, '====自动回复=====\n  回复 {} 即可获取相关信息。').format("、".join(req_key_word))
        else:
            return ''


    elif msg.type == "text":              # 为文本消息

        text_type = Redis.save_uesr_rec(FromUserName)     # 查询用户上次五分钟之内的浏览记录
        send_text = msg.content  # 用户发送的文本消息

        if text_type != False:     # 用户具有上次浏览记录
            text_type = text_type.decode("utf-8")

            if send_text in req_key_word:   # 如果输入为关键词
                Redis.save_uesr_rec(user_id=FromUserName, type='save', rec=send_text)   # 存储本次浏览记录
                ques = que_dict[send_text]
                reply_text = '====自动回复=====\n{}\n  请回复问题前序号, 例"1"'.format(
                    ''.join(["{}.{}\n".format(i, list(ques[i].keys())[0]) for i in ques]))
                return Reply_text(msg, reply_text)

            elif text_type in req_key_word:  # 具有上次浏览记录
                if re.search("(\d+(\.\d+)?)", send_text):   # 如果可以提取出数字
                    Redis.save_uesr_rec(user_id=FromUserName, type='save', rec=text_type)  # 存储本次浏览记录
                    ques_index = re.search("(\d+(\.\d+)?)", send_text).group()
                    try:
                        if "." not in ques_index:  # 询问1级标题
                            ques = list(que_dict[text_type][str(send_text)].values())[0]
                            reply_text = '====自动回复=====\n{}\n  请回复问题前序号, 例"1.1"'.format(
                                ''.join(["{}{}\n".format(i, ques[i]) for i in ques]))
                        else:       # 询问二级标题
                            ques = list(que_dict[text_type][str(send_text.split('.')[0])].values())[0]
                            que_ans = ans_dict[ques[str(send_text)]]
                            if "(图文)" in que_ans:
                                que_ans = que_ans.replace("(图文)", "").split("=")
                                reply_dic = {
                                                'title': que_ans[0],
                                                'description': que_ans[1],
                                                'image': '',
                                                'url': 'https://mp.weixin.qq.com/s/ZuXJAHOPt3y5sRr4hJmhuQ'
                                            }
                                return Reply_Article(msg, reply_dic)
                            reply_text = '====自动回复=====\n{}\n'.format(que_ans)
                    except Exception as e:
                        print("失败 输入信息为 {}-{} {}".format(send_text, text_type, e))
                        reply_text = '====自动回复=====\n  我不懂您的意思, 请回复 {} 即可获取相关信息。'.format("、".join(req_key_word))

                else:  # 无法提取出数字 首先进行模糊匹配 匹配失败 返回 如下
                    pro_que = difflib.get_close_matches(send_text, ans_dict.keys(), 1, cutoff=0.6)
                    if pro_que == []:
                        reply_text = '====自动回复=====\n  我不懂您的意思, 请回复 {} 即可获取相关信息。'.format("、".join(req_key_word))
                    else:
                        que = pro_que[0]
                        que_ans = ans_dict[que]
                        reply_text = '====自动回复=====\n 请问您要询问的问题是否是？\n {} \n回复:{}'.format(que, que_ans)
                return Reply_text(msg, reply_text)


        else:      #  用户不具有上次浏览记录
            if send_text in req_key_word:   # 根据用户回复关键字 返回相关问题
                Redis.save_uesr_rec(user_id=FromUserName, type='save', rec=send_text)   # 存储本次浏览记录
                ques = que_dict[send_text]
                reply_text = '====自动回复=====\n{}\n  请回复问题前序号, 例"1"'.format(
                    ''.join(["{}.{}\n".format(i, list(ques[i].keys())[0]) for i in ques]))
            else:  # 若无关键字 首先进行模糊匹配 匹配失败 返回建议信息

                pro_que = difflib.get_close_matches(send_text, ans_dict.keys(), 1, cutoff=0.6)
                if pro_que == []:
                    reply_text = '====自动回复=====\n  我不懂您的意思, 请回复 {} 即可获取相关信息。'.format("、".join(req_key_word))
                else:
                    que = pro_que[0]
                    que_ans = ans_dict[que]
                    reply_text = '====自动回复=====\n 请问您要询问的问题是否是？\n {} \n回复:{}'.format(que, que_ans)
            return Reply_text(msg, reply_text)


if __name__ == '__main__':
    app.debug = True  # 1.0以后版本不通过本方法启动调试模式
    server = pywsgi.WSGIServer(('0.0.0.0', 80), app)
    server.serve_forever()

    # app.run(debug=True, processes=True)
