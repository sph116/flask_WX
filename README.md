# flask_WX
flask公众号后端 实现多层自动回复 使用gevent将flask优化为异步

## 功能
  根据ques_data.xlsx格式 配置相关问答数据  
  使用redis存储用户行为数据  
  完成多模块 多层自动回复  


## 配置:  
  1.根据 ques_data.xlsx 修改数据 保存原格式  
  2.修改 server.py 验证token  
  3.修改 Check_duplication.py redis配置  
