# CopyMangaDownloader
CopyManga网漫画下载器，基于asyncio实现高速异步下载。
## 使用
1. 安装依赖 `pip install -r requirements.txt`
2. 运行 `python downloader.py`
## 功能
### 漫画下载
输入对应的pathword与章节名即可下载漫画。
pathword是漫画页面url中comic后面的一串字符，章节名要和**官网上给出的章节名一致**。章节名支持范围输入，如：第1话-第10话，使用“-”隔开。
漫画会被下载到工作路径下以官网漫画名命名的文件夹中，每一话也是独立的文件夹存放。
### 追漫
同目录下新建`watching.json`，内容如下：
```json
{
    "pathword" : "最新已看章节"
}
```
如：
```json
{
    "zongzhijiushifeichangkeaiflymetothemoon" : "第174话",
    "xxx" : "第xxx话"
}
```
脚本中提供选项对`watching.json`中的所有漫画进行更新检查，并把未看的新章节自动下载到本地。
## 其他
此脚本是个人在线看漫画过程中因有时加载太慢影响观看体验而编写，主要用于追漫更新。请不要大批量爬取漫画，给网站造成过大压力，谢谢。