# 自动获取酒店源 #

### 感谢 ssili126 大佬开源 https://github.com/ssili126/tv/ ###

使用方法：


  在看电视直播软件中直接输入以下地址即可：
  
      https://raw.githubusercontent.com/nomoneynolife/tv/main/itvlist.txt
  
想自己获取电视直播地址的可采用以下方法：
  
  有安装python的电脑：
  
      电脑安装chrome，下载对应版本的chromedriver
      下载itv.py cctv.py weishi.py qita.py
      pip install selenium requests futures eventlet
      依次运行itv.py cctv.py weishi.py qita.py
      运行完成后在当前目录下生成电视直播文件itvlist.txt
