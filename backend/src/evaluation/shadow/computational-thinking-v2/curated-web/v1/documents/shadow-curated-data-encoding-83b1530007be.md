# 字符编码｜精选补充资料

> 来源：[维基百科（中文）](https://zh.wikipedia.org/wiki/%E5%AD%97%E7%AC%A6%E7%BC%96%E7%A0%81)  
> 许可：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)  
> 语言：简体中文  
> 获取时间：2026-08-08T09:43:34.423223+00:00

维基百科，自由的百科全书

**字符编码**（英語：Character encoding）、**字碼**、**字集碼**是把**字符集**中的[字符](/wiki/%E5%AD%97%E7%AC%A6_(%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A7%91%E5%AD%A6) "字符 (计算机科学)")为指定集合中某一对象（例如：[位元](/wiki/%E4%BD%8D%E5%85%83 "位元")模式、[自然数](/wiki/%E8%87%AA%E7%84%B6%E6%95%B0 "自然数")[序列](/wiki/%E5%BA%8F%E5%88%97 "序列")、[八位元](/wiki/%E5%85%AB%E4%BD%8D%E5%85%83 "八位元")或者[电脉冲](/wiki/%E9%9B%BB%E7%A3%81%E6%B3%A2 "電磁波")），以便[文本](/wiki/%E6%96%87%E6%9C%AC "文本")在[计算机](/wiki/%E7%94%B5%E5%AD%90%E8%AE%A1%E7%AE%97%E6%9C%BA "电子计算机")中存储和通过[通信](/wiki/%E9%80%9A%E4%BF%A1 "通信")网络的传递。

純就字面解釋，這些術語是有不同的概念，但在許多的中文語境，這些術語會混用，有相同的概念。**字符集**，是指「字符的集合」，如中文字符集、英文字符集，不牽涉到編碼。**字符編碼**、字集碼、字碼，則是「對於某個字符集，為其字符編碼」，根據語義，有時指單一字符的編碼，有時是指全部字符的編碼。

在計算機支援語言、文字的過程中，要支援某個文字，必然要搜集所使用的字符，為其編碼，因此，初期並未區分字符集和字符編碼的不同。譬如，[大五碼](/wiki/%E5%A4%A7%E4%BA%94%E7%A2%BC "大五碼")、[國標碼](/wiki/%E5%9B%BD%E6%A0%87%E7%A0%81 "国标码")、[ASCII](/wiki/ASCII "ASCII")既指字符集，又指針對此字符集的編碼方式。在[統一碼](/wiki/%E7%B5%B1%E4%B8%80%E7%A2%BC "統一碼")之後，則細分字符集和編碼形式的不同。同一個字符集，可以有不同的編碼形式，如[UTF-8](/wiki/UTF-8 "UTF-8")、[UTF-16](/wiki/UTF-16 "UTF-16")。

常见的例子包括将[拉丁字母](/wiki/%E6%8B%89%E4%B8%81%E5%AD%97%E6%AF%8D "拉丁字母")表编码成[摩斯电码](/wiki/%E6%91%A9%E6%96%AF%E7%94%B5%E7%A0%81 "摩斯电码")和[ASCII](/wiki/ASCII "ASCII")。其中，[ASCII](/wiki/ASCII "ASCII")将字母、数字和其它符号[編號](/wiki/%E7%BC%96%E5%8F%B7 "编号")，並用7[位元](/wiki/%E4%BD%8D%E5%85%83 "位元")的[二进制](/wiki/%E4%BA%8C%E8%BF%9B%E5%88%B6 "二进制")來表示这个整数。通常會額外使用一个扩充的位元，以便于以1个[字节](/wiki/%E5%AD%97%E8%8A%82 "字节")的方式存储。

在计算机技术发展的早期，如[ASCII](/wiki/ASCII "ASCII")（1963年）和[EBCDIC](/wiki/EBCDIC "EBCDIC")（1964年）这样的**字符集**逐漸成為標準。但这些字符集的局限很快就变得明显，于是人们开发了許多方法来扩展它们。对于支持包括东亚[CJK](/wiki/CJK "CJK")字符家族在内的[写作系统](/wiki/%E6%96%87%E5%AD%97 "文字")的要求能支持更大量的字符，并且需要一种系统而不是临时的方法实现这些字符的编码。

有時，為強調其所使用的方式而使用其他術語，譬如：為說明「電腦系統『內部』
處理文字資料所使用的字符編碼」時，會使用**內碼**。為「不同電腦系統之間，為了『交換』資料所採用的字符編碼」時，會使用**交換碼**。

## 简单字符集

按照惯例，人们认为字符集和字符编码是[同义词](/wiki/%E5%90%8C%E4%B9%89%E8%AF%8D "同义词")，因为使用同样的标准来定义提供什么字符并且这些字符如何编码到一系列的代码单元（通常一个字符一个单元）。由于历史的原因，[MIME](/wiki/MIME "MIME")和使用这种编码的系统使用术语**字符集**来表示用于将一组字符编码成一系列八位字节数据的整个系统。

## 现代编码模型

由[統一碼](/wiki/%E7%B5%B1%E4%B8%80%E7%A2%BC "統一碼")和[通用字符集](/wiki/%E9%80%9A%E7%94%A8%E5%AD%97%E7%AC%A6%E9%9B%86 "通用字符集")所構成的现代字符编码模型則没有跟从简单字符集的观点。它们将字符编码的概念分为：有哪些字符、它们的[编号](/wiki/%E7%BC%96%E5%8F%B7 "编号")、这些[编号](/wiki/%E7%BC%96%E5%8F%B7 "编号")如何编码成一系列的“码元”（有限大小的数字）以及最后这些单元如何組成八位字节流。區分這些概念的核心思想是建立一个能够用不同方法來编码的一个通用字符集。为了正确地表示这个模型需要更多比“字符集”和“字符编码”更为精确的术语表示。在Unicode Technical Report (UTR) #17中，现代编码模型分为5个层次，所用的术语列在下面：

1. **抽象字符表**（Abstract character repertoire）是一个系统支持的所有抽象字符的集合。字符表可以是封闭的，即除非创建一个新的标准（ASCII和多数ISO/IEC 8859系列都是这样的例子），否則不允许添加新的符号；字符表也可以是开放的，即允许添加新的符号（統一碼和一定程度上[代碼頁](/wiki/%E4%BB%A3%E7%A0%81%E9%A1%B5 "代码页")是这方面的例子）。特定字符表中的字符反映了如何将书写系统分解成线性信息单元的决定。例如拉丁、希腊和斯拉夫字母表分为字母、数字、变音符号、标点和如空格这样的一些少数特殊字符，它们都能按照一种简单的线性序列排列（尽管对它们的处理需要另外的规则，如带有变音符号的字母这样的特定序列如何解释——但这不属于字符表的范畴）。为了方便起见，这样的字符表可以包括预先[编号](/wiki/%E7%BC%96%E5%8F%B7 "编号")的[字母](/wiki/%E5%AD%97%E6%AF%8D "字母")和变音符号的组合。其它的书写系统，如阿拉伯语和希伯莱语，由于要适应双向文字和在不同情形下按照不同方式交叉在一起的字形，就使用更为复杂的符号表表示。
2. **编码字符集**（CCS:Coded Character Set）是将字符集



   C
   {\displaystyle C}
   ${\displaystyle C}$中每个字符映射到1个坐标（整数值对：x, y）或者表示为1个非负整数



   N
   {\displaystyle N}
   ${\displaystyle N}$。字符集及码位映射称为编码字符集。例如，在一个给定的字符表中，表示大写拉丁字母“A”的字符被赋予整数65、字符“B”是66，如此继续下去。多个编码字符集可以表示同样的字符表，例如[ISO-8859-1](/wiki/ISO/IEC_8859-1 "ISO/IEC 8859-1")和IBM的[代码页](/wiki/%E4%BB%A3%E7%A0%81%E9%A1%B5 "代码页")037和代码页500含蓋同样的字符表但是将字符映射为不同的[整数](/wiki/%E6%95%B4%E6%95%B0 "整数")。由此产生了**编码空间**（encoding space）的概念：简单说就是包含所有字符的表的维度。可以用一对整数来描述，例如：[GB 2312](/wiki/GB_2312 "GB 2312")的汉字编码空间是94 x 94。可以用一个整数来描述，例如：ISO-8859-1的编码空间是256。也可以用字符的存储单元尺寸来描述，例如：ISO-8859-1是一个8比特的编码空间。编码空间还可以用其子集来表述，如行、列、面（plane）等。编码空间中的一个位置（position）称为**[码位](/wiki/%E7%A0%81%E4%BD%8D "码位")**（code point）。一个字符所占用的码位称为**码位值**（code point value）。1个编码字符集就是把抽象字符映射为码位值。
3. **字符编码表**（CEF:Character Encoding Form），也称为"storage format"，是将编码字符集的非负整数值（即抽象的码位）转换成有限比特长度的整型值（称为**码元**code units）的序列。这对于定长编码来说是个到自身的映射（null mapping），但对于变长编码来说，该映射比较复杂，把一些码位映射到一个码元，把另外一些码位映射到由多个码元组成的序列。例如，使用16比特长的存储单元保存数字信息，系统每个单元只能够直接表示从0到65,535的数值，但是如果使用多个16位单元就能够表示更大的整数。这就是CEF的作用，它可以把Unicode从0到140万的码空间范围的每个码位映射到单个或多个在0到65,535范围内的码值。最简单的字符编码表就是單純地选择足够大的单位，以保证编码字符集中的所有数值能够直接编码（一个码位对应一个码值）。这对于能够用使用八位元组來表示的编码字符集（如多数传统的非CJK的字符集编码）是合理的，对于能够使用十六位元來表示的编码字符集（如早期版本的Unicode）来说也足够合理。但是，随着编码字符集的大小增加（例如，现在的Unicode的字符集至少需要21位才能全部表示），这种直接表示法变得越来越没有效率，并且很难让现有计算机系统适应更大的码值。因此，许多使用新近版本Unicode的系统，或者将Unicode码位對應為可变长度的8位字节序列的[UTF-8](/wiki/UTF-8 "UTF-8")，或者将码位對應为可变长度的16位序列的[UTF-16](/wiki/UTF-16 "UTF-16")。
4. **字符编码方案**（CES:Character Encoding Scheme），也称作"serialization format"。將定长的整型值（即码元）映射到8位字节序列，以便编码后的数据的文件存储或网络传输。在使用Unicode的场合，使用一个简单的字符来指定字节顺序是[大端序](/wiki/%E5%A4%A7%E7%AB%AF%E5%BA%8F "大端序")或者[小端序](/wiki/%E5%B0%8F%E7%AB%AF%E5%BA%8F "小端序")（但对于UTF-8来说并不需要专门指明字节序）。然而，有些复杂的字符编码机制（如[ISO/IEC 2022](/wiki/ISO/IEC_2022 "ISO/IEC 2022")）使用控制字符转义序列在几种编码字符集或者用于减小每个单元所用字节数的压缩机制（如[SCSU](/w/index.php?title=SCSU&action=edit&redlink=1 "SCSU（页面不存在）")、[BOCU](/w/index.php?title=BOCU&action=edit&redlink=1 "BOCU（页面不存在）")和[Punycode](/wiki/Punycode "Punycode")）之间切换。
5. **传输编码语法**（transfer encoding syntax），用于处理上一层次的字符编码方案提供的字节序列。一般其功能包括两种：一是把字节序列的值映射到一套更受限制的值域内，以满足传输环境的限制，例如Email传输时[Base64](/wiki/Base64 "Base64")或者[quoted-printable](/wiki/Quoted-printable "Quoted-printable")，都是把8位的字节编码为7位长的数据；另一是压缩字节序列的值，如[LZW](/wiki/LZW "LZW")或者[行程长度编码](/wiki/%E8%A1%8C%E7%A8%8B%E9%95%BF%E5%BA%A6%E7%BC%96%E7%A0%81 "行程长度编码")等无损压缩技术。

**高层机制**（higher level protocol）提供了额外信息，用于选择Unicode字符的特定变种，如[XML](/wiki/XML "XML")属性xml:lang

**字符映射**（character map）在Unicode中保持了其传统意义：从字符序列到编码后的字节序列的映射，包括了上述的CCS, CEF, CES层次。

## 字符集、代码页，与字符映射

术语字符编码（character encoding），字符映射（character map），字符集（character set）或者[代码页](/wiki/%E4%BB%A3%E7%A0%81%E9%A1%B5 "代码页")，在历史上往往是同义概念，即字符表（repertoire）中的字符如何编码为码元的流（stream of code units）–通常每个字符对应单个码元。

码元（Code Unit，也称「代码单元」）是指一个已编码的文本中具有最短的比特组合的单元。对于[UTF-8](/wiki/UTF-8 "UTF-8")来说，码元是8比特长；对于[UTF-16](/wiki/UTF-16 "UTF-16")来说，码元是16比特长；对于[UTF-32](/wiki/UTF-32 "UTF-32")来说，码元是32比特长。码值（Code Value）是过时的用法。

代码页通常意味着面向字节的编码，但强调是一套用于不能语言的编码方案的集合.著名的如"Windows"代码页系列，"IBM"/"DOS"代码页系列.

IBM的字符数据表示体系（Character Data Representation Architecture - CDRA）与[编码字符集标识符](/w/index.php?title=CCSID&action=edit&redlink=1 "CCSID（页面不存在）")（coded character set identifiers - CCSIDs） 常常把charset, character set, code page, or CHARMAP等类似意义的术语混用.

Unix或Linux不使用代码页概念，它们用charmap，比locales具有更广泛的含义.

与上文的编码字符集（Coded Character Set - CCS）不同，字符编码（character encoding）是从抽象字符到代码字（code word）的映射. HTTP（与MIME）的用法中，字符集（character set）与字符编码同义，但与CCS不是一个意思.

## 字符编码（不全）

* [ASCII](/wiki/ASCII "ASCII")
* [EBCDIC](/wiki/EBCDIC "EBCDIC")

### 西欧标准

* [ISO-8859-1](/wiki/ISO-8859-1 "ISO-8859-1")
* [ISO-8859-5](/wiki/ISO_8859-5 "ISO 8859-5")
* [ISO-8859-6](/wiki/ISO_8859-6 "ISO 8859-6")
* [ISO-8859-7](/wiki/ISO_8859-7 "ISO 8859-7")
* [ISO-8859-11](/wiki/ISO-8859-11 "ISO-8859-11")
* [ISO-8859-15](/wiki/ISO_8859-15 "ISO 8859-15")
* [ISO/IEC 646](/wiki/ISO/IEC_646 "ISO/IEC 646")

### DOS字符集（又称IBM[代码页](/wiki/%E4%BB%A3%E7%A0%81%E9%A1%B5 "代码页")）

* [CP437](/w/index.php?title=Code_page_437&action=edit&redlink=1 "Code page 437（页面不存在）")
* [CP737](/w/index.php?title=Code_page_737&action=edit&redlink=1 "Code page 737（页面不存在）")
* [CP850](/w/index.php?title=Code_page_850&action=edit&redlink=1 "Code page 850（页面不存在）")
* [CP852](/w/index.php?title=Code_page_852&action=edit&redlink=1 "Code page 852（页面不存在）")
* [CP855](/w/index.php?title=Code_page_855&action=edit&redlink=1 "Code page 855（页面不存在）")
* [CP857](/w/index.php?title=Code_page_857&action=edit&redlink=1 "Code page 857（页面不存在）")
* [CP858](/w/index.php?title=Code_page_858&action=edit&redlink=1 "Code page 858（页面不存在）")
* [CP860](/w/index.php?title=Code_page_860&action=edit&redlink=1 "Code page 860（页面不存在）")
* [CP861](/w/index.php?title=Code_page_861&action=edit&redlink=1 "Code page 861（页面不存在）")
* [CP863](/w/index.php?title=Code_page_863&action=edit&redlink=1 "Code page 863（页面不存在）")
* [CP865](/w/index.php?title=Code_page_865&action=edit&redlink=1 "Code page 865（页面不存在）")
* [CP866](/w/index.php?title=Code_page_866&action=edit&redlink=1 "Code page 866（页面不存在）")
* [CP869](/w/index.php?title=Code_page_869&action=edit&redlink=1 "Code page 869（页面不存在）")

### [Windows](/wiki/Microsoft_Windows "Microsoft Windows")字符集

* [Windows-1250](/w/index.php?title=Windows-1250&action=edit&redlink=1 "Windows-1250（页面不存在）")
* [Windows-1251](/w/index.php?title=Windows-1251&action=edit&redlink=1 "Windows-1251（页面不存在）")：用于西里尔字母表
* [Windows-1252](/wiki/Windows-1252 "Windows-1252")
* [Windows-1253](/w/index.php?title=Windows-1253&action=edit&redlink=1 "Windows-1253（页面不存在）")
* [Windows-1254](/w/index.php?title=Windows-1254&action=edit&redlink=1 "Windows-1254（页面不存在）")
* [Windows-1255](/w/index.php?title=Windows-1255&action=edit&redlink=1 "Windows-1255（页面不存在）")：用于[希伯莱语](/wiki/%E5%B8%8C%E4%BC%AF%E8%90%8A%E8%AA%9E "希伯萊語")
* [Windows-1256](/w/index.php?title=Windows-1256&action=edit&redlink=1 "Windows-1256（页面不存在）")：用于[阿拉伯语](/wiki/%E9%98%BF%E6%8B%89%E4%BC%AF%E8%AF%AD "阿拉伯语")
* [Windows-1257](/w/index.php?title=Windows-1257&action=edit&redlink=1 "Windows-1257（页面不存在）")
* [Windows-1258](/w/index.php?title=Windows-1258&action=edit&redlink=1 "Windows-1258（页面不存在）")：用于[越南语](/wiki/%E8%B6%8A%E5%8D%97%E8%AF%AD "越南语")

### 亞洲字符集

尤其是**漢字編碼**。

#### 臺灣

* [大五碼](/wiki/%E5%A4%A7%E4%BA%94%E7%A2%BC "大五碼")
* [中文資訊交換碼](/wiki/%E4%B8%AD%E6%96%87%E8%B3%87%E8%A8%8A%E4%BA%A4%E6%8F%9B%E7%A2%BC "中文資訊交換碼")
* [中文標準交換碼](/wiki/%E4%B8%AD%E6%96%87%E6%A8%99%E6%BA%96%E4%BA%A4%E6%8F%9B%E7%A2%BC "中文標準交換碼")
* [EUC](/wiki/EUC#EUC-TW "EUC")

#### 中國大陸及港澳

* [GB/T 2312](/wiki/GB_2312 "GB 2312")
* [GB/T 12345](/wiki/GB_12345 "GB 12345")
* [EUC](/wiki/EUC#EUC-CN "EUC")
* [GBK](/wiki/GBK "GBK")（规定文件为GB13000）
* [GB 18030](/wiki/GB_18030 "GB 18030")
* [香港增補字符集](/wiki/%E9%A6%99%E6%B8%AF%E5%A2%9E%E8%A3%9C%E5%AD%97%E7%AC%A6%E9%9B%86 "香港增補字符集")

#### 日本

* [ISO/IEC 2022](/wiki/ISO/IEC_2022 "ISO/IEC 2022")
* [Shift JIS](/wiki/Shift_JIS "Shift JIS")
* [EUC](/wiki/EUC#EUC-JP "EUC")

#### 朝鲜半岛

* [EUC](/wiki/EUC#EUC-KR "EUC")
* [KOI8-R](/wiki/KOI8-R "KOI8-R")
* [KOI8-U](/wiki/KOI8-U "KOI8-U")
* KOI7
* MIK Code page

#### 越南

* [越南資訊交換標準代碼](/wiki/%E8%B6%8A%E5%8D%97%E8%B3%87%E8%A8%8A%E4%BA%A4%E6%8F%9B%E6%A8%99%E6%BA%96%E4%BB%A3%E7%A2%BC "越南資訊交換標準代碼")

#### 印度

* [印度文字資訊交換碼](/wiki/%E5%8D%B0%E5%BA%A6%E6%96%87%E5%AD%97%E8%B3%87%E8%A8%8A%E4%BA%A4%E6%8F%9B%E7%A2%BC "印度文字資訊交換碼")

#### 統一碼

* [統一碼](/wiki/%E7%B5%B1%E4%B8%80%E7%A2%BC "統一碼")
* [UTF-7](/wiki/UTF-7 "UTF-7")
* [UTF-8](/wiki/UTF-8 "UTF-8")
* [UTF-16](/wiki/UTF-16 "UTF-16")
* [UTF-32](/wiki/UTF-32 "UTF-32")

## 字符转换工具

由于有很多种字符编码方法被使用，从一种字符编码转换到另一种，需要一些工具。

[跨平台](/wiki/%E8%B7%A8%E5%B9%B3%E5%8F%B0 "跨平台")：

* [网页浏览器](/wiki/%E7%BD%91%E9%A1%B5%E6%B5%8F%E8%A7%88%E5%99%A8 "网页浏览器")–大多数现代的网页浏览器都具有此功能。一般是在菜单"查看"（View）/"字符编码"（Character Encoding）
* [iconv](/wiki/Iconv "Iconv") –程序与编程API，用于字符编码转换
* convert\_encoding.py –基于[Python](/wiki/Python "Python")的转换工具.
* decodeh.py –用于启发性猜测编码方案的算法与模块.
* [國際統一碼部件](/wiki/%E5%9C%8B%E9%9A%9B%E7%B5%B1%E4%B8%80%E7%A2%BC%E9%83%A8%E4%BB%B6 "國際統一碼部件") –一套[C语言](/wiki/C%E8%AF%AD%E8%A8%80 "C语言")与[Java](/wiki/Java "Java")语言的开源库，由[IBM](/wiki/IBM "IBM")提供，用于統一碼等多语言编码的转换、实现.
* [chardet](https://web.archive.org/web/20130114161259/http://chardet.feedparser.org/) – [Mozilla](/wiki/Mozilla "Mozilla")的编码自动检测代码的Python语言实现.
* 新版本的Unix命令[File](/wiki/File_(%E5%91%BD%E4%BB%A4) "File (命令)")做字符编码的检测.（[cygwin](/wiki/Cygwin "Cygwin")与[mac](/wiki/MacOS "MacOS")都有此命令）

[Linux](/wiki/Linux "Linux"):

* recode –
* utrac – 将整个文件内容从一种字符编码转换到另外一种
* cstocs –
* convmv –转换文件名.
* enca –分析编码模式.

[Microsoft Windows](/wiki/Microsoft_Windows "Microsoft Windows"):

* Encoding.Convert – .NET API
* MultiByteToWideChar/WideCharToMultiByte – Windows API
* cscvt –转换工具
* enca –分析编码方法

## 參見

* [Category:字符编码](/wiki/Category:%E5%AD%97%E7%AC%A6%E7%BC%96%E7%A0%81 "Category:字符编码")—关于通用字符编码的文章
* [Category:字符集](/wiki/Category:%E5%AD%97%E7%AC%A6%E9%9B%86 "Category:字符集")—关于特殊字符编码的文章
* [亂碼](/wiki/%E4%BA%82%E7%A2%BC "亂碼")—非映射字符集
* [代码页](/wiki/%E4%BB%A3%E7%A0%81%E9%A1%B5 "代码页")
* [字形](/wiki/%E5%AD%97%E5%BD%A2 "字形")
* [位圖](/wiki/%E4%BD%8D%E5%9B%BE "位图")
* [像素](/wiki/%E5%83%8F%E7%B4%A0 "像素")
* [體素](/wiki/%E9%AB%94%E7%B4%A0 "體素")
* [中文軟體](/wiki/%E4%B8%AD%E6%96%87%E8%BB%9F%E9%AB%94 "中文軟體")

1. **[^](#cite_ref-1)** [Glossary of Unicode Terms](http://unicode.org/glossary/).  [2012-04-07]. （原始内容[存档](https://web.archive.org/web/20151226015034/http://www.unicode.org/glossary/)于2015-12-26）.
2. **[^](#cite_ref-2)** [Homepage of Michael Goerz – convert\_encoding.py](https://web.archive.org/web/20101028073152/http://users.physik.fu-berlin.de/~mgoerz/blog/programs/convert_encoding/).  [2012-03-23]. （[原始内容](http://users.physik.fu-berlin.de/~mgoerz/blog/programs/convert_encoding/)存档于2010-10-28）.
3. **[^](#cite_ref-3)** [Decodeh – heuristically decode a string or text file](https://web.archive.org/web/20080108123255/http://gizmojo.org/code/decodeh/).  [2012-03-23]. （[原始内容](http://gizmojo.org/code/decodeh/)存档于2008-01-08）.
4. **[^](#cite_ref-4)** [Recode – GNU Project – Free Software Foundation (FSF)](http://www.gnu.org/software/recode/recode.html).  [2012-03-23]. （原始内容[存档](https://web.archive.org/web/20210210230722/http://www.gnu.org/software/recode/recode.html)于2021-02-10）.
5. **[^](#cite_ref-5)** [Utrac Homepage](http://utrac.sourceforge.net/).  [2006-05-12]. （原始内容[存档](https://web.archive.org/web/20210125190013/http://utrac.sourceforge.net/)于2021-01-25）.
6. **[^](#cite_ref-6)** [Convmv – converts filenames from one encoding to another](https://www.j3e.de/linux/convmv/man/).  [2012-03-23]. （原始内容[存档](https://web.archive.org/web/20180611013429/https://www.j3e.de/linux/convmv/man/)于2018-06-11）.
7. **[^](#cite_ref-7)** [Extremely Naive Charset Analyser](https://web.archive.org/web/20101204060724/http://directory.fsf.org/project/enca/).  [2012-03-23]. （[原始内容](http://directory.fsf.org/project/enca/)存档于2010-12-04）.
8. **[^](#cite_ref-8)** [Microsoft .NET Framework Class Library – Encoding.Convert Method](https://web.archive.org/web/20120421164654/http://msdn.microsoft.com/en-us/library/system.text.encoding.convert(VS.71).aspx).  [2012-03-23]. （[原始内容](http://msdn.microsoft.com/en-us/library/system.text.encoding.convert(VS.71).aspx)存档于2012-04-21）.
9. **[^](#cite_ref-9)** [MultiByteToWideChar/WideCharToMultiByte – Convert from ANSI to Unicode & Unicode to ANSI](http://support.microsoft.com/kb/138813).  [2012-03-23]. （原始内容[存档](https://web.archive.org/web/20150212083132/http://support.microsoft.com/kb/138813/)于2015-02-12）.
10. **[^](#cite_ref-10)** [Character Set Converter](https://web.archive.org/web/20120326122821/http://www.kalytta.com/tools.php).  [2012-03-23]. （[原始内容](http://www.kalytta.com/tools.php)存档于2012-03-26）.
11. **[^](#cite_ref-11)** [Extremely Naive Charset Analyser](https://web.archive.org/web/20120315090223/http://www.john.geek.nz/2010/02/enca-binary-compiled-for-32-bit-windows/).  [2012-03-23]. （[原始内容](http://www.john.geek.nz/2010/02/enca-binary-compiled-for-32-bit-windows/)存档于2012-03-15）.

* [Character sets registered by Internet Assigned Numbers Authority](http://www.iana.org/assignments/character-sets)（[页面存档备份](//web.archive.org/web/20040716042926/http://www.iana.org/assignments/character-sets)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [Unicode Technical Report #17: Character Encoding Model](https://web.archive.org/web/20050323094939/http://www.unicode.org/unicode/reports/tr17/)
* [SIL's freeware fonts, editors and documentation](http://scripts.sil.org/cms/scripts/page.php?site_id=nrsi&id=) （[页面存档备份](//web.archive.org/web/20210113145834/http://scripts.sil.org/cms/scripts/page.php?site_id=nrsi&id=)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")） See [SIL](/wiki/SIL%E5%9C%8B%E9%9A%9B "SIL國際")
* [ICU Converter Explorer](http://demo.icu-project.org/icu-bin/convexp) （[页面存档备份](//web.archive.org/web/20200102215631/http://demo.icu-project.org/icu-bin/convexp)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [The Cyrillic Charset soup](http://czyborra.com/charsets/cyrillic.html)（[页面存档备份](//web.archive.org/web/20161203230933/http://czyborra.com/charsets/cyrillic.html)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [Early history of character set standardization](https://web.archive.org/web/20100116001012/http://homepages.cwi.nl/~dik/english/codes/stand.html)
* [Character Sets And Code Pages At The Push Of A Button](http://www.i18nguy.com/unicode/codepages.html) （[页面存档备份](//web.archive.org/web/20201107224708/http://www.i18nguy.com/unicode/codepages.html)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [A complete introduction to Japanese character encodings](https://web.archive.org/web/20060527013315/http://www.cs.mcgill.ca/~aelias4/encodings.html)
* [A tutorial on character code issues](http://www.cs.tut.fi/~jkorpela/chars.html) （[页面存档备份](//web.archive.org/web/20170917131301/http://www.cs.tut.fi/~jkorpela/chars.html)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [Online Char (ASCII), HEX, Binary, Base64, etc... Encoder/Decoder with MD2, MD4, MD5, SHA1+2, etc. hashing algorithms](http://arquivo.pt/wayback/20100530092446/http%3A//home1.paulschou.net/tools/xlate/)
* [Universal Cyrillic decoder](http://www.2cyr.com/decode/) （[页面存档备份](//web.archive.org/web/20210214004643/http://www.2cyr.com/decode/)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）,一个用来帮助恢复由于错误字符编码产生的不可读的[西里尔字母](/wiki/%E8%A5%BF%E9%87%8C%E5%B0%94%E5%AD%97%E6%AF%8D "西里尔字母")的在线程序（以及其它的一些程序）.
* [Introduction to i18n](http://www.debian.org/doc/manuals/intro-i18n/)（[页面存档备份](//web.archive.org/web/20050729013402/http://www.debian.org/doc/manuals/intro-i18n/)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")），请参阅Chapter 3 - Important Concepts for Character Coding Systems
* [汉字字符编码查询](https://web.archive.org/web/20090708003902/http://xxcx.org/hzbm/)
* [精确解释Unicode](http://blog.csdn.net/gqqnb/article/details/6266542) （[页面存档备份](//web.archive.org/web/20190522080359/http://blog.csdn.net/gqqnb/article/details/6266542)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）

[分类](/wiki/Special:Categories "Special:Categories")：​

* [字符编码](/wiki/Category:%E5%AD%97%E7%AC%A6%E7%BC%96%E7%A0%81 "Category:字符编码")

隐藏分类：​

* [自2014年2月需补充来源的条目](/wiki/Category:%E8%87%AA2014%E5%B9%B42%E6%9C%88%E9%9C%80%E8%A1%A5%E5%85%85%E6%9D%A5%E6%BA%90%E7%9A%84%E6%9D%A1%E7%9B%AE "Category:自2014年2月需补充来源的条目")
* [拒绝当选首页新条目推荐栏目的条目](/wiki/Category:%E6%8B%92%E7%BB%9D%E5%BD%93%E9%80%89%E9%A6%96%E9%A1%B5%E6%96%B0%E6%9D%A1%E7%9B%AE%E6%8E%A8%E8%8D%90%E6%A0%8F%E7%9B%AE%E7%9A%84%E6%9D%A1%E7%9B%AE "Category:拒绝当选首页新条目推荐栏目的条目")
* [含有英語的條目](/wiki/Category:%E5%90%AB%E6%9C%89%E8%8B%B1%E8%AA%9E%E7%9A%84%E6%A2%9D%E7%9B%AE "Category:含有英語的條目")
