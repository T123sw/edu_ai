```CNKI.py```文件中是CNKI抓取逻辑  
```get_PDF_links_by_keywords.py```中是pdf抓取逻辑  
```Selenium_get_html.py```中是txt抓取逻辑  
```crawle_url,py```中是抓取指定url得逻辑
```setup.py```中设置输出地址、关键词、抓取页数、指定的url


抓pdf运行```main_pdf.py```  
抓txt运行```main_txt.py```  
抓CNKI运行```main_cnki.py```  
抓指定得url运行```main_urls.py```
#### 注意
**运行时需要访问外网，所以得用ip**  
**关键词不要用多个，只能写一个**  
**指定得url可以有多个，用`\n`分隔**

#### 输出文件
```plaintext
output/
├── 关键词/
│   ├── CNKI/
│   │   └── xxx.pdf
│   └── collect/
│       ├── pdf/
│       │   └── xxx.pdf
│       └── text/
│           └── xxx.txt
└── urls/
    ├── pdf/
    │   └── xxx.pdf
    └── text/
        └── xxx.txt
```   