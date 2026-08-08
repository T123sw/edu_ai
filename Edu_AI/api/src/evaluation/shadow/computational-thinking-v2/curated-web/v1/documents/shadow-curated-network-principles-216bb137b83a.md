# TCP/IP 协议族｜精选补充资料

> 来源：[维基百科（中文）](https://zh.wikipedia.org/wiki/TCP/IP%E5%8D%8F%E8%AE%AE%E6%97%8F)  
> 许可：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)  
> 语言：简体中文  
> 获取时间：2026-08-08T09:44:13.595660+00:00

维基百科，自由的百科全书

（重定向自[TCP/IP协议族](/w/index.php?title=TCP/IP%E5%8D%8F%E8%AE%AE%E6%97%8F&redirect=no "TCP/IP协议族")）

**互联网协议套件**（英語：Internet Protocol Suite）是一種网络通訊模型，以及用於[网络传输的协议](/wiki/%E7%BD%91%E7%BB%9C%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "网络传输协议")集合，為[網際网络](/wiki/%E7%BD%91%E9%99%85%E7%BD%91%E7%BB%9C "网际网络")的基礎通訊架構，被應用於各種網絡通信中。

它常通稱為**TCP/IP协议族**（英語：TCP/IP Protocol Suite），简称**TCP/IP**。该協定家族的兩個核心協定：TCP（[传输控制协议](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")）和IP（[网际协议](/wiki/%E7%BD%91%E9%99%85%E5%8D%8F%E8%AE%AE "网际协议")），為该家族中最早通過的標準。由於在網絡通讯协议普遍采用分层的结构，当多个层次的协议共同工作时，类似计算机科学中的[堆栈](/wiki/%E5%A0%86%E6%A0%88 "堆栈")，因此又称为**TCP/IP协议栈**（英語：TCP/IP Stack）。这些协议最早发源于[美国国防部](/wiki/%E7%BE%8E%E5%9B%BD%E5%9B%BD%E9%98%B2%E9%83%A8 "美国国防部")（縮寫為DoD）的[ARPA网](/wiki/ARPA%E7%BD%91 "ARPA网")项目，因此也稱作**DoD模型**（DoD Model）。這個協定套組由[互联网工程任务组](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E5%B7%A5%E7%A8%8B%E4%BB%BB%E5%8A%A1%E7%BB%84 "互联网工程任务组")負責維護。

TCP/IP提供了點對點連結的機制，將資料應該如何封裝、定址、傳輸、路由以及在目的地如何接收，都加以標準化。它將軟體通信過程[抽象化](/wiki/%E6%8A%BD%E8%B1%A1%E5%8C%96_(%E8%A8%88%E7%AE%97%E6%A9%9F%E7%A7%91%E5%AD%B8) "抽象化 (計算機科學)")為四個[抽象層](/wiki/%E6%8A%BD%E8%B1%A1%E5%B1%A4 "抽象層")，採取[協定堆疊](/w/index.php?title=%E5%8D%94%E5%AE%9A%E5%A0%86%E7%96%8A&action=edit&redlink=1 "協定堆疊（页面不存在）")的方式，分別實作出不同通信協定。協定套組下的各種協定，依其功能分別歸屬到這四個階層之中。

TCP/IP模型通常視為簡化的七層[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")。一般認為TCP/IP的連結層相當於OSI/RM的實體層及資料鏈結層。不過，[思科](/wiki/%E6%80%9D%E7%A7%91 "思科")認為此模型並不包含實體層，只能對應OSI的其中6層。

## 歷史

### 研發初期

1983年1月1日，在[因特网](/wiki/%E5%9B%A0%E7%89%B9%E7%BD%91 "因特网")的前身（ARPA网）中通訊方式換成新的定義，TCP/IP取代旧的[网络控制协议](/wiki/%E7%BD%91%E7%BB%9C%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "网络控制协议")（NCP，Network Control Protocol），从而成为今天的互联网的基石。最早的TCP/IP由[文顿·瑟夫](/wiki/%E6%96%87%E9%A1%BF%C2%B7%E7%91%9F%E5%A4%AB "文顿·瑟夫")和[罗伯特·卡恩](/wiki/%E7%BD%97%E4%BC%AF%E7%89%B9%C2%B7%E5%8D%A1%E6%81%A9 "罗伯特·卡恩")两位开发，慢慢地通过竞争战胜其他一些网络协议的方案，比如[国际标准化组织](/wiki/%E5%9B%BD%E9%99%85%E6%A0%87%E5%87%86%E5%8C%96%E7%BB%84%E7%BB%87 "国际标准化组织")[ISO](/wiki/ISO "ISO")的[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")。TCP/IP的蓬勃发展发生在1990年代中期。当时一些重要而可靠的工具的出世，例如页面描述语言[HTML](/wiki/HTML "HTML")和浏览器[Mosaic](/wiki/Mosaic "Mosaic")，促成了互联网应用的飞速发展。
随着互联网的发展，目前流行的[IPv4](/wiki/IPv4 "IPv4")协议（网际协议版本四）已经接近它的功能上限。IPv4最致命的两个缺陷在于：

* 地址只有32位，[IP地址](/wiki/IP%E5%9C%B0%E5%9D%80 "IP地址")空间有限；
* 不支持服务质量（[Quality of Service](/wiki/QoS "QoS")，QoS），无法管理带宽和优先级，故而不能很好的支持现今越来越多实时的语音和视频应用。因此[IPv6](/wiki/IPv6 "IPv6")（网际协议版本六）浮出水面，用以取代IPv4。

TCP/IP成功的另一个因素在於对为数众多的低层协议的支持。这些低层协议对应[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")中的第一层（物理层）和第二层（数据链路层）。每层的所有协议几乎都有一半数量支持TCP/IP，例如：[以太网](/wiki/%E4%BB%A5%E5%A4%AA%E7%BD%91 "以太网")（Ethernet）、[令牌环](/wiki/%E4%BB%A4%E7%89%8C%E7%8E%AF "令牌环")（Token Ring）、[光纤数据分布接口](/wiki/%E5%85%89%E7%BA%A4%E5%88%86%E5%B8%83%E5%BC%8F%E6%95%B0%E6%8D%AE%E6%8E%A5%E5%8F%A3 "光纤分布式数据接口")（FDDI）、[点对点协议](/wiki/%E7%82%B9%E5%AF%B9%E7%82%B9%E5%8D%8F%E8%AE%AE "点对点协议")（PPP）、[X.25](/wiki/X.25 "X.25")、[帧中继](/wiki/%E5%B8%A7%E4%B8%AD%E7%BB%A7 "帧中继")（Frame Relay）、[ATM](/wiki/%E5%BC%82%E6%AD%A5%E4%BC%A0%E8%BE%93%E6%A8%A1%E5%BC%8F "异步传输模式")、[Sonet](/wiki/%E5%90%8C%E6%AD%A5%E5%85%89%E7%BD%91%E7%BB%9C "同步光网络")、[SDH](/wiki/SDH "SDH")等通訊方法中都可以應用。

### 標準化

## 研制背景

最初想到让不同电脑之间实现连接的，是美国[加州大学洛杉矶分校](/wiki/%E5%8A%A0%E5%B7%9E%E5%A4%A7%E5%AD%A6%E6%B4%9B%E6%9D%89%E7%9F%B6%E5%88%86%E6%A0%A1 "加州大学洛杉矶分校")网络工作小组的[斯蒂芬·克罗克](/wiki/%E6%96%AF%E8%92%82%E8%8A%AC%C2%B7%E5%85%8B%E7%BD%97%E5%85%8B "斯蒂芬·克罗克")（Stephen D. Crocker）。1970年，克罗克及其小组着手制定最初的主机对主机通信协议，它称为**网络控制协议**（Network Control Protocol，缩写NCP）。该协议用于[阿帕网](/wiki/%E9%98%BF%E5%B8%95%E7%BD%91 "阿帕网")，并在局部网络条件下运行稳定，但随着阿帕网的用户增多，NCP逐渐暴露出两大缺陷：

1. NCP只是一台主机对另一台主机的通讯协议，并未给网络中的每台电脑设置唯一的地址，導致电脑在越来越庞大的网络中难以准确定位需要传输数据的对象。
2. NCP缺乏纠错功能，数据在传输过程中一旦出现错误，网络就可能停止运行，而隨著出错的电脑增多，网络运行效率也將大打折扣。

## 开发过程

在构建[阿帕网](/wiki/%E9%98%BF%E5%B8%95%E7%BD%91 "阿帕网")先驱之后，DARPA开始其他数据传输技术的研究。NCP诞生后两年，1972年，[罗伯特·卡恩](/wiki/%E7%BD%97%E4%BC%AF%E7%89%B9%C2%B7%E5%8D%A1%E6%81%A9 "罗伯特·卡恩")（Robert E. Kahn）受僱於DARPA的[信息技术处理办公室](/w/index.php?title=%E4%BF%A1%E6%81%AF%E6%8A%80%E6%9C%AF%E5%A4%84%E7%90%86%E5%8A%9E%E5%85%AC%E5%AE%A4&action=edit&redlink=1 "信息技术处理办公室（页面不存在）")，在那里他研究卫星数据包网络和地面无线数据包网络，并且意识到能够在它们之间沟通的价值。

在1973年春天，已有的ARPANET网络控制程序（NCP）协议的开发者[文顿·瑟夫](/wiki/%E6%96%87%E9%A1%BF%C2%B7%E7%91%9F%E5%A4%AB "文顿·瑟夫")（Vinton Cerf）加入到卡恩为ARPANET设计下一代协议而开发开放互连模型的工作中。到了1973年夏天，卡恩和瑟夫很快开发出基本的改进形式，其中的网络协议之间的差异通过使用公用[互联网协议](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E5%8D%8F%E8%AE%AE "互联网协议")而隐藏起来，且可靠性由主机保证而不是ARPANET那样由网络保证。瑟夫称赞了[Hubert Zimmerman](/w/index.php?title=Hubert_Zimmerman&action=edit&redlink=1 "Hubert Zimmerman（页面不存在）")和[Louis Pouzin](/wiki/Louis_Pouzin "Louis Pouzin")（[CYCLADES](/w/index.php?title=CYCLADES&action=edit&redlink=1 "CYCLADES（页面不存在）")网络的设计者）在这个设计上发挥重要影响。

由于网络的作用减少到最小的程度，更有可能将任何网络连接到一起，而不用管它们不同的特点，这样能解决卡恩最初的问题。流行的说法提到瑟夫和卡恩工作的最终产品[TCP/IP](/wiki/TCP/IP "TCP/IP")将在运行“两个罐子和一根弦”上，实际上它已经用在[信鸽](/wiki/IP_over_Avian_Carriers "IP over Avian Carriers")上。一个称为网关（后来改为[路由器](/wiki/%E8%B7%AF%E7%94%B1%E5%99%A8 "路由器")以免与[网关](/wiki/%E7%BD%91%E5%85%B3 "网关")混淆）的计算机为每个网络提供一个接口并且在它们之间来回传输[数据包](/wiki/%E6%95%B0%E6%8D%AE%E5%8C%85 "数据包")。这个设计思想更细的形式由瑟夫在斯坦福的网络研究组的1973年–1974年期间开发出来。处于同一时期诞生[PARC通用包](/w/index.php?title=PARC%E9%80%9A%E7%94%A8%E5%8C%85&action=edit&redlink=1 "PARC通用包（页面不存在）")协议组的[施乐PARC](/w/index.php?title=%E6%96%BD%E4%B9%90PARC&action=edit&redlink=1 "施乐PARC（页面不存在）")早期网络研究工作也有着重要的技术影响；人们在两者之间摇摆不定。DARPA于是与[BBN](/wiki/BBN%E7%A7%91%E6%8A%80 "BBN科技")、斯坦福和伦敦大学签署协议开发不同硬件平台上协议的运行版本。有四个版本开发出来——TCPv1、TCPv2、在1978年春天分成TCPv3和IPv3的版本，后来就是稳定的TCP/IPv4——目前因特网仍然使用的标准协议。

1975年，两个网络之间的TCP/IP通信在斯坦福和伦敦大学（UCL）之间进行测试。1977年11月，三个网络之间的TCP/IP测试在美国、英国和挪威之间进行。在1978年到1983年间，其他一些TCP/IP原型在多个研究中心之间开发出来。ARPANET完全转换到TCP/IP在1983年1月1日发生。1984年，美国国防部将TCP/IP作为所有计算机网络的标准。1985年，因特网架构理事会举行爲期三天有250家厂商代表参加的关于计算产业使用TCP/IP的工作会议，帮助协议的推广并且引领它日渐增长的商业应用。

2005年9月9日卡恩和瑟夫由于对美国文化的卓越贡献獲[总统自由勋章](/wiki/%E6%80%BB%E7%BB%9F%E8%87%AA%E7%94%B1%E5%8B%8B%E7%AB%A0 "总统自由勋章")。

## TCP/IP協議棧組成

整個通信網絡的任務，可以劃分成不同的功能區塊，即所謂的層級（[layer](/w/index.php?title=Layer&action=edit&redlink=1 "Layer（页面不存在）")）。用於互聯網的協議可以比照[TCP/IP參考模型](#TCP/IP参考模型)進行分類。TCP/IP協議棧起始於第三層協議IP（[網際協議](/wiki/%E7%B6%B2%E9%9A%9B%E5%8D%94%E8%AD%B0 "網際協議")）。所有這些協議都在相應的[RFC](/wiki/RFC "RFC")文檔中討論及標準化。重要的協議在相應的[RFC](/wiki/RFC "RFC")文檔中均標記狀態：“必須”（required），“推薦”（recommended），“可選”（selective）。其他的協議還可能有“試驗”（experimental）或“歷史”（historic）的狀態。”

## 必须协议

所有的TCP/IP应用都必须实现IP和[ICMP](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%8E%A7%E5%88%B6%E6%B6%88%E6%81%AF%E5%8D%8F%E8%AE%AE "互联网控制消息协议")。对于一个[路由器](/wiki/%E8%B7%AF%E7%94%B1%E5%99%A8 "路由器")（router）而言，有这两个协议就可以运作，虽然从应用的角度来看，这样一个[路由器](/wiki/%E8%B7%AF%E7%94%B1%E5%99%A8 "路由器")意义不大。实际的路由器一般还需要运行许多「推荐」使用的协议，以及一些其他的协议。
几乎所有连接到互联网上的電腦上都存在的IPv4协议出生在1981年，今天的版本和最早的版本并没有多少改变。升级版IPv6的工作始于1995年，目的在于取代IPv4。ICMP协议主要用于收集有关网络的信息查找错误等工作。

## TCP/IP参考模型

|  |
| --- |
| 两个因特网主机通过两个路由器和对应的层连接。各主机上的应用通过一些数据通道相互执行读取操作。 |
| [RFC 1122](https://datatracker.ietf.org/doc/html/rfc1122)中描述的沿着不同的层应用数据的封装递减 |

**TCP/IP参考模型**是一个抽象的分层模型，这个模型中，所有的[TCP/IP](/wiki/TCP/IP "TCP/IP")系列[网络协议](/wiki/%E7%BD%91%E7%BB%9C%E5%8D%8F%E8%AE%AE "网络协议")都归类到4个抽象的「层」中。每一抽象层建立在低一层提供的服务上，并且为高一层提供服务。

完成一些特定的任务需要众多的协议协同工作，这些协议分布在参考模型的不同层中的，因此有时称它们为一个[协议栈](/wiki/%E5%8D%8F%E8%AE%AE%E6%A0%88 "协议栈")。TCP/IP参考模型为[TCP/IP](/wiki/TCP/IP "TCP/IP")协议栈订身制作。其中IP协议只关心如何使得数据能够跨越本地网络边界的问题，而不关心如何利用传输媒体，数据如何传输。整个[TCP/IP](/wiki/TCP/IP "TCP/IP")协议栈则负责解决数据如何通过许许多多个点对点通路（一个点对点通路，也称为一「跳」，1 hop）顺利传输，由此不同的网络成员能够在许多「跳」的基础上建立相互的数据通路。如想分析更普遍的网络通信问题，ISO的[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")也能起更好的帮助作用。

**因特网协议族**是一组实现支持[因特网](/wiki/%E5%9B%A0%E7%89%B9%E7%BD%91 "因特网")和大多数商业网络运行的[协议栈](/wiki/%E5%8D%8F%E8%AE%AE%E6%A0%88 "协议栈")的[网络传输协议](/wiki/%E7%BD%91%E7%BB%9C%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "网络传输协议")。它有时也称为**TCP/IP协议组**，这个名称来源于其中两个最重要的协议：[传输控制协议](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")（[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")）和[因特网协议](/wiki/%E7%BD%91%E9%99%85%E5%8D%8F%E8%AE%AE "网际协议")（[IP](/wiki/%E7%BD%91%E9%99%85%E5%8D%8F%E8%AE%AE "网际协议")），它们也是最先定义的两个协议。同许多其他协议一样[网络传输协议](/wiki/%E7%BD%91%E7%BB%9C%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "网络传输协议")也可以看作一个多层组合，每层解决数据传输中的一组问题并且向使用这些低层服务的高层提供定义好的服务。高层逻辑上与用户更为接近，所处理[数据](/wiki/%E6%95%B0%E6%8D%AE "数据")更为抽象，它们依赖于低层将数据转换成最终能够进行實體控制的形式。[网络传输协议](/wiki/%E7%BD%91%E7%BB%9C%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "网络传输协议")能够大致匹配到一些厂商喜欢使用的固定7层的[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")。然而这些层并非都能够很好地与基于IP的网络对应（根据应用的设计和支持网络的不同它们确实是涉及到不同的层）并且一些人认为试图将[因特网协议组](/w/index.php?title=%E5%9B%A0%E7%89%B9%E7%BD%91%E5%8D%8F%E8%AE%AE%E7%BB%84&action=edit&redlink=1 "因特网协议组（页面不存在）")对应到OSI会带来混淆而不是有所帮助。

### 因特网协议栈中的层

人们已经进行一些讨论关于如何将[TCP/IP参考模型](#TCP/IP参考模型)映射到[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")。由于[TCP/IP](/wiki/TCP/IP "TCP/IP")和[OSI](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")模型组不能精确地匹配，还没有一个完全正确的答案。

另外，[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")下层还不具备能够真正占据真正层的位置的能力；在传输层和网络层之间还需要另外一个层（网络互连层）。特定网络类型专用的一些协议应该运行在网络层上，但是却运行在基本的硬件帧交换上。类似协议的例子有[ARP](/wiki/%E5%9C%B0%E5%9D%80%E8%A7%A3%E6%9E%90%E5%8D%8F%E8%AE%AE "地址解析协议")和[STP](/wiki/%E7%94%9F%E6%88%90%E6%A0%91%E5%8D%8F%E8%AE%AE "生成树协议")（用来保持冗余[网桥](/w/index.php?title=Network_bridge&action=edit&redlink=1 "Network bridge（页面不存在）")的空闲状态直到真正需要它们）。

然而，它们是本地协议并且在网络互连功能下面运行。不可否认，将两个组（更不用说它们只是运行在如[ICMP](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%8E%A7%E5%88%B6%E6%B6%88%E6%81%AF%E5%8D%8F%E8%AE%AE "互联网控制消息协议")等不同的互连网络协议上的逻辑上的网络层的一部分）整个放在同一层会引起混淆，但是OSI模型还没有复杂到能够做更好的工作。

下面的图表试图显示不同的TCP/IP和其他的协议在最初[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")中的位置：

|  |  |  |
| --- | --- | --- |
| 7 | **应用层** application layer | 例如[HTTP](/wiki/%E8%B6%85%E6%96%87%E6%9C%AC%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "超文本传输协议")、[SMTP](/wiki/%E7%AE%80%E5%8D%95%E9%82%AE%E4%BB%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "简单邮件传输协议")、[SNMP](/wiki/%E7%AE%80%E5%8D%95%E7%BD%91%E7%BB%9C%E7%AE%A1%E7%90%86%E5%8D%8F%E8%AE%AE "简单网络管理协议")、[FTP](/wiki/%E6%96%87%E4%BB%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "文件传输协议")、[Telnet](/wiki/Telnet "Telnet")、[SIP](/wiki/%E4%BC%9A%E8%AF%9D%E5%8F%91%E8%B5%B7%E5%8D%8F%E8%AE%AE "会话发起协议")、[SSH](/wiki/Secure_Shell "Secure Shell")、[NFS](/wiki/%E7%BD%91%E7%BB%9C%E6%96%87%E4%BB%B6%E7%B3%BB%E7%BB%9F "网络文件系统")、[RTSP](/wiki/RTSP "RTSP")、[XMPP](/wiki/XMPP "XMPP")、[Whois](/wiki/WHOIS "WHOIS")、[ENRP](/w/index.php?title=ENRP&action=edit&redlink=1 "ENRP（页面不存在）")（英语：[Endpoint\_Handlespace\_Redundancy\_Protocol](https://en.wikipedia.org/wiki/Endpoint_Handlespace_Redundancy_Protocol "en:Endpoint Handlespace Redundancy Protocol")）、[TLS](/wiki/%E5%82%B3%E8%BC%B8%E5%B1%A4%E5%AE%89%E5%85%A8%E6%80%A7%E5%8D%94%E5%AE%9A "傳輸層安全性協定") |
| 6 | **表示层** presentation layer | 例如[XDR](/wiki/%E5%A4%96%E9%83%A8%E6%95%B0%E6%8D%AE%E8%A1%A8%E7%A4%BA%E6%B3%95 "外部数据表示法")、[ASN.1](/wiki/ASN.1 "ASN.1")、[NCP](/wiki/%E7%BD%91%E7%BB%9C%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "网络控制协议")、[TLS](/wiki/TLS "TLS")、[ASCII](/wiki/ASCII "ASCII") |
| 5 | **会话层** session layer | 例如[ASAP](/w/index.php?title=ASAP&action=edit&redlink=1 "ASAP（页面不存在）")（英语：[Aggregate\_Server\_Access\_Protocol](https://en.wikipedia.org/wiki/Aggregate_Server_Access_Protocol "en:Aggregate Server Access Protocol")）、ISO 8327 / CCITT X.225、[RPC](/wiki/%E9%81%A0%E7%A8%8B%E9%81%8E%E7%A8%8B%E8%AA%BF%E7%94%A8 "遠程過程調用")、[NetBIOS](/wiki/NetBIOS "NetBIOS")、[Winsock](/wiki/Winsock "Winsock")、[BSD sockets](/wiki/Berkeley%E5%A5%97%E6%8E%A5%E5%AD%97 "Berkeley套接字")、[SOCKS](/wiki/SOCKS "SOCKS")、[PAP](/w/index.php?title=%E5%AF%86%E7%A2%BC%E9%A9%97%E8%AD%89%E5%8D%94%E8%AD%B0&action=edit&redlink=1 "密碼驗證協議（页面不存在）") |
| 4 | **传输层** transport layer | 例如[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")、[UDP](/wiki/%E7%94%A8%E6%88%B7%E6%95%B0%E6%8D%AE%E6%8A%A5%E5%8D%8F%E8%AE%AE "用户数据报协议")、[RTP](/wiki/%E5%AE%9E%E6%97%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "实时传输协议")、[SCTP](/wiki/%E6%B5%81%E6%8E%A7%E5%88%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "流控制传输协议")、[SPX](/wiki/%E5%BA%8F%E5%88%97%E5%88%86%E7%B5%84%E4%BA%A4%E6%8F%9B "序列分組交換")、[ATP](/wiki/AppleTalk "AppleTalk")、[IL](/w/index.php?title=IL_Protocol&action=edit&redlink=1 "IL Protocol（页面不存在）") |
| 3 | **网络层** network layer | 例如[IP](/wiki/%E7%BD%91%E9%99%85%E5%8D%8F%E8%AE%AE "网际协议")、[ICMP](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%8E%A7%E5%88%B6%E6%B6%88%E6%81%AF%E5%8D%8F%E8%AE%AE "互联网控制消息协议")、[IPX](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E5%88%86%E7%BB%84%E4%BA%A4%E6%8D%A2%E5%8D%8F%E8%AE%AE "互联网分组交换协议")、[BGP](/wiki/%E8%BE%B9%E7%95%8C%E7%BD%91%E5%85%B3%E5%8D%8F%E8%AE%AE "边界网关协议")、[OSPF](/wiki/OSPF "OSPF")、[RIP](/wiki/%E8%B7%AF%E7%94%B1%E4%BF%A1%E6%81%AF%E5%8D%8F%E8%AE%AE "路由信息协议")、[IGRP](/wiki/IGRP "IGRP")、[EIGRP](/wiki/EIGRP "EIGRP")、[ARP](/wiki/%E5%9C%B0%E5%9D%80%E8%A7%A3%E6%9E%90%E5%8D%8F%E8%AE%AE "地址解析协议")、[RARP](/wiki/RARP "RARP")、[X.25](/wiki/X.25 "X.25") |
| 2 | **数据链路层** data link layer | 例如[以太网](/wiki/%E4%BB%A5%E5%A4%AA%E7%BD%91 "以太网")、[令牌环](/wiki/%E4%BB%A4%E7%89%8C%E7%8E%AF "令牌环")、[HDLC](/wiki/HDLC "HDLC")、[帧中继](/wiki/%E5%B8%A7%E4%B8%AD%E7%BB%A7 "帧中继")、[ISDN](/wiki/ISDN "ISDN")、[ATM](/wiki/%E5%BC%82%E6%AD%A5%E4%BC%A0%E8%BE%93%E6%A8%A1%E5%BC%8F "异步传输模式")、[IEEE 802.11](/wiki/IEEE_802.11 "IEEE 802.11")、[FDDI](/wiki/FDDI "FDDI")、[PPP](/wiki/%E7%82%B9%E5%AF%B9%E7%82%B9%E5%8D%8F%E8%AE%AE "点对点协议") |
| 1 | **物理层** physical layer | 例如[數據機](/wiki/%E6%95%B8%E6%93%9A%E6%A9%9F "數據機")、[无线电](/wiki/%E6%97%A0%E7%BA%BF%E7%94%B5 "无线电")、[光纤](/wiki/%E5%85%89%E7%BA%A4 "光纤") |

通常人们认为OSI模型的最上面三层（应用层、表示层和会话层）在TCP/IP组中是一个应用层。由于TCP/IP有一个相对较弱的会话层，由TCP和RTP下的打开和关闭连接组成，并且在TCP和UDP下的各种应用提供不同的端口号，这些功能能够由单个的应用程序（或者那些应用程序所使用的库）增加。

与此相似的是，IP是按照将它下面的网络当作一个黑盒子的思想设计的，这样在讨论TCP/IP的时候就可以把它当作一个独立的层。

|  |  |  |
| --- | --- | --- |
| 4 | **应用层** application layer | 例如[HTTP](/wiki/%E8%B6%85%E6%96%87%E6%9C%AC%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "超文本传输协议")、[FTP](/wiki/%E6%96%87%E4%BB%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "文件传输协议")、[DNS](/wiki/DNS "DNS")  *（如[BGP](/wiki/%E8%BE%B9%E7%95%8C%E7%BD%91%E5%85%B3%E5%8D%8F%E8%AE%AE "边界网关协议")和[RIP](/wiki/%E8%B7%AF%E7%94%B1%E4%BF%A1%E6%81%AF%E5%8D%8F%E8%AE%AE "路由信息协议")这样的路由协议，尽管由于各种各样的原因它们分别运行在TCP和UDP上，仍然可以将它们看作网络层的一部分）* |
| 3 | **传输层** transport layer | 例如[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")、[UDP](/wiki/%E7%94%A8%E6%88%B7%E6%95%B0%E6%8D%AE%E6%8A%A5%E5%8D%8F%E8%AE%AE "用户数据报协议")、[RTP](/wiki/RTP "RTP")、[SCTP](/wiki/SCTP "SCTP")  *（如[OSPF](/wiki/OSPF "OSPF")这样的路由协议，尽管运行在IP上也可以看作是网络层的一部分）* |
| 2 | **网络互连层** internet layer | 对于TCP/IP来说这是[因特网协议](/wiki/%E5%9B%A0%E7%89%B9%E7%BD%91%E5%8D%8F%E8%AE%AE "因特网协议")（IP） *（如[ICMP](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%8E%A7%E5%88%B6%E6%B6%88%E6%81%AF%E5%8D%8F%E8%AE%AE "互联网控制消息协议")和[IGMP](/wiki/%E5%9B%A0%E7%89%B9%E7%BD%91%E7%BB%84%E7%AE%A1%E7%90%86%E5%8D%8F%E8%AE%AE "因特网组管理协议")这样的必须协议尽管运行在IP上，也仍然可以看作是网络互连层的一部分；[ARP](/wiki/%E5%9C%B0%E5%9D%80%E8%A7%A3%E6%9E%90%E5%8D%8F%E8%AE%AE "地址解析协议")不运行在IP上）* |
| 1 | **网络存取（連結）层** Network Access (link) layer | 例如[以太网](/wiki/%E4%BB%A5%E5%A4%AA%E7%BD%91 "以太网")、[Wi-Fi](/wiki/Wi-Fi "Wi-Fi")、[MPLS](/wiki/%E5%A4%9A%E5%8D%8F%E8%AE%AE%E6%A0%87%E7%AD%BE%E4%BA%A4%E6%8D%A2 "多协议标签交换")等。 |

#### 应用层

该层包括所有和应用程序协同工作，利用基础网络交换应用程序专用的数据的协议。
[应用层](/wiki/%E5%BA%94%E7%94%A8%E5%B1%82 "应用层")是大多数普通与网络相关的程序为了通过网络与其他程序通信所使用的层。这个层的处理过程是应用特有的；数据从网络相关的程序以这种应用内部使用的格式进行传送，然后编码成标准协议的格式。

一些特定的程序視爲在此層運行。它们提供服务直接支持用户应用。这些程序和它们对应的协议包括[HTTP](/wiki/%E8%B6%85%E6%96%87%E6%9C%AC%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "超文本传输协议")（万维网服务）、[FTP](/wiki/%E6%96%87%E4%BB%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "文件传输协议")（文件传输）、[SMTP](/wiki/%E7%AE%80%E5%8D%95%E9%82%AE%E4%BB%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "简单邮件传输协议")（电子邮件）、[SSH](/wiki/Secure_Shell "Secure Shell")（安全远程登录）、[DNS](/wiki/%E5%9F%9F%E5%90%8D%E7%B3%BB%E7%BB%9F "域名系统")（名称⇔IP地址寻找）以及许多其他协议。

一旦从应用程序来的数据编码成一个标准的应用层协议，它将传送到IP栈的下一层。

在传输层，应用程序最常用的是TCP或者UDP，并且服务器应用程序经常与一个[公开的端口号](/wiki/TCP/UDP%E7%AB%AF%E5%8F%A3%E5%88%97%E8%A1%A8 "TCP/UDP端口列表")相联系。服务器应用程序的端口由[互联网号码分配局](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E5%8F%B7%E7%A0%81%E5%88%86%E9%85%8D%E5%B1%80 "互联网号码分配局")（IANA）正式地分配，但是现今一些新协议的开发者经常选择它们自己的端口号。由于在同一个系统上很少超过少数几个的服务器应用，端口冲突引起的问题很少。应用软件通常也允许用户强制性地指定端口号作为运行[参数](/wiki/%E5%8F%83%E6%95%B8_(%E7%A8%8B%E5%BC%8F%E8%A8%AD%E8%A8%88) "參數 (程式設計)")。

连结外部的客户端程序通常使用系统分配的一个随机端口号。监听一个端口并且通过服务器将那个端口发送到应用的另外一个副本以建立对等连结（如[IRC](/wiki/IRC "IRC")上的[dcc](/w/index.php?title=Dcc&action=edit&redlink=1 "Dcc（页面不存在）")文件传输）的应用也可以使用一个随机端口，但是应用程序通常允许定义一个特定的端口范围的规范以允许端口能够通过实现[网络地址转换](/wiki/%E7%BD%91%E7%BB%9C%E5%9C%B0%E5%9D%80%E8%BD%AC%E6%8D%A2 "网络地址转换")（NAT）的路由器映射到内部。

每一个应用层（[TCP/IP参考模型](#TCP/IP参考模型)的最高层）协议一般都会使用到两个传输层协议之一：
面向连接的[TCP传输控制协议](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")和无连接的包传输的[UDP用户数据报文协议](/wiki/%E7%94%A8%E6%88%B7%E6%95%B0%E6%8D%AE%E6%8A%A5%E5%8D%8F%E8%AE%AE "用户数据报协议")。
常用的应用层协议有：

:   运行在[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")协议上的协议：

    :   * [HTTP](/wiki/%E8%B6%85%E6%96%87%E6%9C%AC%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "超文本传输协议")（Hypertext Transfer Protocol，超文本传输协议），主要用于普通浏览。
        * [HTTPS](/wiki/%E8%B6%85%E6%96%87%E6%9C%AC%E4%BC%A0%E8%BE%93%E5%AE%89%E5%85%A8%E5%8D%8F%E8%AE%AE "超文本传输安全协议")（Hypertext Transfer Protocol over Secure Socket Layer，or HTTP over SSL，安全超文本传输协议），HTTP协议的安全版本。
        * [FTP](/wiki/%E6%96%87%E4%BB%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "文件传输协议")（File Transfer Protocol，文件传输协议），由名知义，用于文件传输。
        * [POP3](/wiki/%E9%83%B5%E5%B1%80%E5%8D%94%E5%AE%9A "郵局協定")（Post Office Protocol，version 3，邮局协议），收邮件用。
        * [SMTP](/wiki/%E7%AE%80%E5%8D%95%E9%82%AE%E4%BB%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "简单邮件传输协议")（Simple Mail Transfer Protocol，简单邮件传输协议），用来发送电子邮件。
        * [TELNET](/wiki/Telnet "Telnet")（Teletype over the Network，网络电传），通过一个终端（terminal）登陆到网络。
        * [SSH](/wiki/Secure_Shell "Secure Shell")（Secure Shell，用于替代安全性差的[TELNET](/wiki/TELNET "TELNET")），用于加密安全登陆用。
:   运行在[UDP](/wiki/%E7%94%A8%E6%88%B7%E6%95%B0%E6%8D%AE%E6%8A%A5%E5%8D%8F%E8%AE%AE "用户数据报协议")协议上的协议：

    :   * [BOOTP](/wiki/BOOTP "BOOTP")（Boot Protocol，启动协议），应用于无盘设备。
        * [NTP](/wiki/%E7%B6%B2%E8%B7%AF%E6%99%82%E9%96%93%E5%8D%94%E5%AE%9A "網路時間協定")（Network Time Protocol，网络时间协议），用于网络同步。
        * [DHCP](/wiki/%E5%8A%A8%E6%80%81%E4%B8%BB%E6%9C%BA%E8%AE%BE%E7%BD%AE%E5%8D%8F%E8%AE%AE "动态主机设置协议")（Dynamic Host Configuration Protocol，动态主机配置协议），动态配置IP地址。
:   其他：

    :   * [DNS](/wiki/%E5%9F%9F%E5%90%8D%E7%B3%BB%E7%BB%9F "域名系统")（Domain Name Service，域名服务），用于完成地址查找，邮件转发等工作（运行在[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")和[UDP](/wiki/%E7%94%A8%E6%88%B7%E6%95%B0%E6%8D%AE%E6%8A%A5%E5%8D%8F%E8%AE%AE "用户数据报协议")协议上）。
        * [ECHO](/w/index.php?title=ECHO&action=edit&redlink=1 "ECHO（页面不存在）")（英语：[Echo\_Protocol](https://en.wikipedia.org/wiki/Echo_Protocol "en:Echo Protocol")）（Echo Protocol，回绕协议），用于查错及测量应答时间（运行在[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")和[UDP](/wiki/%E7%94%A8%E6%88%B7%E6%95%B0%E6%8D%AE%E6%8A%A5%E5%8D%8F%E8%AE%AE "用户数据报协议")协议上）。
        * [SNMP](/wiki/%E7%AE%80%E5%8D%95%E7%BD%91%E7%BB%9C%E7%AE%A1%E7%90%86%E5%8D%8F%E8%AE%AE "简单网络管理协议")（Simple Network Management Protocol，简单网络管理协议），用于网络信息的收集和网络管理。
        * [ARP](/wiki/%E5%9C%B0%E5%9D%80%E8%A7%A3%E6%9E%90%E5%8D%8F%E8%AE%AE "地址解析协议")（Address Resolution Protocol，地址解析协议），用于动态解析以太网硬件的地址。

#### 传输层

[传输层](/wiki/%E4%BC%A0%E8%BE%93%E5%B1%82 "传输层")（transport layer）的协议，能够解决诸如端到端可靠性（“数据是否已经到达目的地？”）和保证数据按照正确的顺序到达这样的问题。在TCP/IP协议组中，传输协议也包括所给数据应该送给哪个应用程序。
在TCP/IP协议组中技术上位于这个层的动态路由协议通常认为是网络层的一部分；一个例子就是[OSPF](/wiki/OSPF "OSPF")（IP协议89）。
[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")（IP协议6）是一个“可靠的”、[面向连结](/wiki/%E9%80%A3%E6%8E%A5%E5%B0%8E%E5%90%91%E5%BC%8F%E9%80%9A%E8%A8%8A "連接導向式通訊")的传输机制，它提供一种可靠的字节流保证数据完整、无损并且按顺序到达。TCP尽量连续不断地测试网络的负载并且控制发送数据的速度以避免网络过载。另外，TCP试图将数据按照规定的顺序发送。这是它与UDP不同之处，这在实时数据流或者路由高[网络层](/wiki/%E7%BD%91%E7%BB%9C%E5%B1%82 "网络层")丢失率应用的时候可能成为一个缺陷。
较新的[SCTP](/wiki/%E6%B5%81%E6%8E%A7%E5%88%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "流控制传输协议")也是一个“可靠的”、[面向连结](/wiki/%E9%80%A3%E6%8E%A5%E5%B0%8E%E5%90%91%E5%BC%8F%E9%80%9A%E8%A8%8A "連接導向式通訊")的传输机制。它是面向记录而不是面向字节的，它在一个单独的连结上提供通过多路复用提供的多个子流。它也提供多路自寻址支持，其中连结终端能够以多个IP地址表示（代表多个實體接口），这样的话即使其中一个连接失败了也不中断。它最初是为电话应用开发的（在[IP](/wiki/%E7%BD%91%E9%99%85%E5%8D%8F%E8%AE%AE "网际协议")上传输[SS7](/wiki/%E4%B8%83%E5%8F%B7%E4%BF%A1%E4%BB%A4%E7%B3%BB%E7%BB%9F "七号信令系统")），但是也可以用于其他的应用。
[UDP](/wiki/%E7%94%A8%E6%88%B7%E6%95%B0%E6%8D%AE%E6%8A%A5%E5%8D%8F%E8%AE%AE "用户数据报协议")（IP协议号17）是一个[无连结](/wiki/%E7%84%A1%E9%80%A3%E6%8E%A5%E5%BC%8F%E9%80%9A%E8%A8%8A "無連接式通訊")的数据报协议。它是一个“尽力传递”（best effort）或者说“不可靠”协议——不是因为它特别不可靠，而是因为它不检查数据包是否已经到达目的地，并且不保证它们按顺序到达。如果一个应用程序需要这些特性，那它必须自行检测和判断，或者使用[TCP](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")协议。
UDP的典型性应用是如流媒体（音频和视频等）这样按时到达比可靠性更重要的应用，或者如[DNS](/wiki/DNS "DNS")查找这样的简单查询／响应应用，如果建立可靠的连结所作的额外工作将是不成比例地大。
[DCCP](/wiki/DCCP "DCCP")目前正由IETF开发。它提供TCP流动控制语义，但对于用户来说保留UDP的数据报服务模型。
TCP和UDP都用来支持一些高层的应用。任何给定网络地址的应用通过它们的TCP或者UDP*[端口号](/wiki/TCP/UDP%E7%AB%AF%E5%8F%A3%E5%88%97%E8%A1%A8 "TCP/UDP端口列表")*区分。根据惯例使一些*大众所知的端口*与特定的应用相联系。
[RTP](/wiki/%E5%AE%9E%E6%97%B6%E4%BC%A0%E8%BE%93%E5%8D%8F%E8%AE%AE "实时传输协议")是为如音频和视频流这样的实时数据设计的数据报协议。RTP是使用UDP包格式作为基础的会话层，然而据说它位于因特网协议栈的传输层。

#### 网络互连层

*TCP/IP协议族中的**网络互连层**（internet layer）在OSI模型中叫做**网络层**（network layer）。*

正如最初所定义的，[网络层](/wiki/%E7%BD%91%E7%BB%9C%E5%B1%82 "网络层")解决在一个单一网络上传输数据包的问题。类似的协议有[X.25](/wiki/X.25 "X.25")和[ARPANET](/wiki/ARPANET "ARPANET")的[Host/IMP Protocol](/w/index.php?title=Host/IMP_Protocol&action=edit&redlink=1 "Host/IMP Protocol（页面不存在）")。
随着[因特网](/wiki/Internet "Internet")思想的出现，在这个层上添加附加的功能，也就是将数据从源[网络](/w/index.php?title=Computer_network&action=edit&redlink=1 "Computer network（页面不存在）")传输到目的网络。这就牵涉到在网络组成的网上选择路径将数据包传输，也就是[因特网](/wiki/%E5%9B%A0%E7%89%B9%E7%BD%91 "因特网")。
在因特网协议组中，[IP](/wiki/%E7%BD%91%E9%99%85%E5%8D%8F%E8%AE%AE "网际协议")完成数据从源发送到目的的基本任务。IP能够承载多种不同的高层协议的数据；这些协议使用一个唯一的*IP协议号*进行标识。ICMP和IGMP分别是1和2。
一些IP承载的协议，如[ICMP](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%8E%A7%E5%88%B6%E6%B6%88%E6%81%AF%E5%8D%8F%E8%AE%AE "互联网控制消息协议")（用来发送关于IP发送的诊断信息）和[IGMP](/wiki/%E5%9B%A0%E7%89%B9%E7%BD%91%E7%BB%84%E7%AE%A1%E7%90%86%E5%8D%8F%E8%AE%AE "因特网组管理协议")（用来管理[多播](/wiki/%E5%A4%9A%E6%92%AD "多播")数据），它们位于IP层之上但是完成网络层的功能，这表明因特网和OSI模型之间的不兼容性。所有的路由协议，如[BGP](/wiki/Border_Gateway_Protocol "Border Gateway Protocol")、[OSPF](/wiki/OSPF "OSPF")、和[RIP](/wiki/%E8%B7%AF%E7%94%B1%E4%BF%A1%E6%81%AF%E5%8D%8F%E8%AE%AE "路由信息协议")实际上也是网络层的一部分，尽管它们似乎应该属于更高的协议栈。

#### 网络存取（连结）层

网络存取（连结）层实际上并不是因特网协议组中的一部分，但是它是数据包从一个设备的网络层传输到另外一个设备的网络层的方法。这个过程能够在[网卡](/wiki/%E7%BD%91%E5%8D%A1 "网卡")的[软件](/wiki/%E8%BD%AF%E4%BB%B6 "软件")[驱动程序](/wiki/%E9%A9%B1%E5%8A%A8%E7%A8%8B%E5%BA%8F "驱动程序")中控制，也可以在[韧体](/wiki/%E9%9F%A7%E4%BD%93 "韧体")或者专用[芯片](/wiki/%E8%8A%AF%E7%89%87 "芯片")中控制。这将完成如添加[报头](/wiki/%E6%8A%A5%E5%A4%B4 "报头")准备发送、通过[實體](/wiki/Physical_layer "Physical layer")[媒介](/w/index.php?title=Transmission_medium&action=edit&redlink=1 "Transmission medium（页面不存在）")实际发送这样一些[数据链路](/wiki/Data_link_layer "Data link layer")功能。另一端，链路层将完成数据帧接收、去除报头并且将接收到的包传到网络层。
然而，链路层并不经常这样简单。它也可能是一个[虚拟专有网络](/wiki/%E8%99%9A%E6%8B%9F%E4%B8%93%E6%9C%89%E7%BD%91%E7%BB%9C "虚拟专有网络")（VPN）或者隧道，在这里从网络层来的包使用[隧道协议](/wiki/%E9%9A%A7%E9%81%93%E5%8D%8F%E8%AE%AE "隧道协议")和其他（或者同样的）协议组发送而不是发送到實體的接口上。VPN和通道通常预先建好，并且它们有一些直接发送到實體接口所没有的特殊特点（例如，它可以加密经过它的数据）。由于现在链路“层”是一个完整的网络，这种协议组的[递归](/wiki/%E9%80%92%E5%BD%92_(%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A7%91%E5%AD%A6) "递归 (计算机科学)")使用可能引起混淆。但是它是一个实现常见复杂功能的一个优秀方法。（尽管需要注意预防一个已经封装并且经隧道发送下去的数据包进行再次地封装和发送）。

### IP網路如何併吞競爭的網路

在長期的發展過程中，IP逐漸取代其他網路。這裏是簡單的解釋。IP传输通用数据。数据能够用于任何目的，并且能够很轻易地取代以前由专有数据网络传输的数据。下面是普通的过程：

1. 一个用于特定目的所开发出来的网络。如果它順利工作，用户将能使用它。
2. 为了提供便利的IP服务，经常用于访问电子邮件或者聊天，通常以某种方式通过专有网络隧道实现。隧道方式最初可能非常没有效率，因为电子邮件和聊天只需要很低的带宽。
3. 通过一点点的投资IP基础设施逐渐在专有数据网络周边出现。
4. 用IP取代专有服务的需求出现，经常是一个用户要求。
5. IP替代品过程遍布整个因特网，这使IP替代品比最初的专有网络更加有价值（由于[网络效应](/wiki/%E7%BD%91%E7%BB%9C%E6%95%88%E5%BA%94 "网络效应")）。
6. 专有网络受到压制。许多用户开始维护使用IP替代品的复制品。
7. IP包的间接开销很小，少于1%，这样在成本上非常有竞争性。人们开发能够将IP带到专有网络上的大部分用户的不昂贵的传输媒介。
8. 大多数用户为削减开销而取消专有网络。

### 实现

* [KA9Q](/w/index.php?title=KA9Q&action=edit&redlink=1 "KA9Q（页面不存在）")PPJ
* [lwIP](/wiki/LwIP "LwIP")

如今，大多数商业操作系统包括TCP/IP栈并且缺省安装它们，对于大多数用户来说，没有必要去探求它们如何实现。TCP/IP包含在所有的商业Unix和Linux发布包中，同样也包含在Mac OS X、Windows系统和Windows Server中。

* [互联网主题](/wiki/Portal:%E4%BA%92%E8%81%94%E7%BD%91 "Portal:互联网")

* [IPv4](/wiki/IPv4 "IPv4")
* [IPv6](/wiki/IPv6 "IPv6")
* [NCP](/wiki/%E7%BD%91%E7%BB%9C%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "网络控制协议")
* [OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")
* [MPLS](/wiki/%E5%A4%9A%E5%8D%8F%E8%AE%AE%E6%A0%87%E7%AD%BE%E4%BA%A4%E6%8D%A2 "多协议标签交换")
* [DoD模型](/wiki/DoD%E6%A8%A1%E5%9E%8B "DoD模型")
* [TCP/UDP端口列表](/wiki/TCP/UDP%E7%AB%AF%E5%8F%A3%E5%88%97%E8%A1%A8 "TCP/UDP端口列表")

1. **[^](#cite_ref-1)** [RFC 1349](https://datatracker.ietf.org/doc/html/rfc1349)，[RFC 2502](https://datatracker.ietf.org/doc/html/rfc2502)
2. **[^](#cite_ref-2)** [RFC 1140](https://datatracker.ietf.org/doc/html/rfc1140)，[RFC 1160](https://datatracker.ietf.org/doc/html/rfc1160)，[RFC 1180](https://datatracker.ietf.org/doc/html/rfc1180)
3. **[^](#cite_ref-3)** Craig Hunt著《TCP/IP网络管理》第一章〈TCP/IP概論〉：「TCP/IP這名稱代表一整套資料通訊協定的組合，這套組合得名於其中兩項最重要的協定：傳輸控制協定（TCP）與網際協定（IP）。之所以強調這一點，是為了強調TCP/IP其實還包含TCP和IP之外的其他成員，只不過這兩項是其中最具代表性的協定。因此，TCP/IP協定組也稱為網際网络協定套組（IPS），這兩個名稱是同義的。」
4. **[^](#cite_ref-4)** [谢希仁](/wiki/%E8%B0%A2%E5%B8%8C%E4%BB%81 "谢希仁"). 计算机网络. 北京: [电子工业出版社](/wiki/%E7%94%B5%E5%AD%90%E5%B7%A5%E4%B8%9A%E5%87%BA%E7%89%88%E7%A4%BE "电子工业出版社"). 2008: 30. [ISBN 9787121053863](/wiki/Special:BookSources/9787121053863 "Special:BookSources/9787121053863").
5. **[^](#cite_ref-5)** Andrew G. Blank. TCP/IP Foundations. New Jersey: John Wiley & Sons. 2006: 2. [ISBN 9780782143706](/wiki/Special:BookSources/9780782143706 "Special:BookSources/9780782143706").
6. **[^](#cite_ref-6)** ["The DoD Internet Architecture Model"](http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.88.7505&rep=rep1&type=pdf) （[页面存档备份](//web.archive.org/web/20131005002826/http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.88.7505&rep=rep1&type=pdf)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）, Vinton G. Cerf and Edward Cain, *Computer Networks*, 7 (1983), North-Holland, pp. 307-318
7. **[^](#cite_ref-7)** [RFC 1122](https://datatracker.ietf.org/doc/html/rfc1122), *Requirements for Internet Hosts – Communication Layers*, R. Braden (ed.), October 1989.
8. **[^](#cite_ref-8)** [RFC 1123](https://datatracker.ietf.org/doc/html/rfc1123), *Requirements for Internet Hosts – Application and Support*, R. Braden (ed.), October 1989
9. **[^](#cite_ref-5VTuU_9-0)** Dye, Mark; McDonald, Rick; Rufi, Antoon. [Network Fundamentals, CCNA Exploration Companion Guide](https://books.google.com/books?id=JVAk7r6jHF4C). Cisco Press. 29 October 2007  [12 September 2016]. [ISBN 9780132877435](/wiki/Special:BookSources/9780132877435 "Special:BookSources/9780132877435") –通过Google Books.
10. **[^](#cite_ref-10)** [存档副本](https://web.archive.org/web/20000303225821/http://www.livinginternet.com/i/ii.htm).  [2007-08-21]. （[原始内容](http://www.livinginternet.com/i/ii.htm)存档于2000-03-03）.
11. **[^](#cite_ref-11)** [存档副本](http://news.bbc.co.uk/1/hi/technology/4415326.stm).  [2007-08-21]. （原始内容[存档](https://web.archive.org/web/20080210004013/http://news.bbc.co.uk/1/hi/technology/4415326.stm)于2008-02-10）.
12. **[^](#cite_ref-12)** [Architectural Principles of the Internet](ftp://ftp.rfc-editor.org/in-notes/rfc1958.txt), [RFC 1958](https://datatracker.ietf.org/doc/html/rfc1958), B. Carpenter, June 1996

* [RFC 1180](https://datatracker.ietf.org/doc/html/rfc1180) TCP/IP指南，因特网工程任务组，1991年1月
* [TCP/IP常见问题解答](http://www.itprc.com/tcpipfaq/)（[页面存档备份](//web.archive.org/web/20070905160410/http://www.itprc.com/tcpipfaq/)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [ARPANET TCP/IP摘要研究](http://www.columbia.edu/~rh120/other/tcpdigest_paper.txt)（[页面存档备份](//web.archive.org/web/20171018152329/http://www.columbia.edu/~rh120/other/tcpdigest_paper.txt)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [TCP/IP流程图](http://www.eventhelix.com/RealtimeMantra/Networking/)（[页面存档备份](//web.archive.org/web/20070821000308/http://www.eventhelix.com/RealtimeMantra/Networking/)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [实践中的因特网](https://web.archive.org/web/20070811215938/http://www.searchandgo.com/articles/internet/internet-practice-4.php)
* [TCP/IP Definition](http://www.linfo.org/tcp_ip.html)（[页面存档备份](//web.archive.org/web/20130923061639/http://www.linfo.org/tcp_ip.html)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [TCP/IP协议集详细资料](http://www.cnpaf.net/class/tcpandip/)（[页面存档备份](//web.archive.org/web/20051001063307/http://www.cnpaf.net/class/tcpandip/)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [uIP](https://web.archive.org/web/20070927213504/http://www.emb-kb.com/doku.php/%E8%A9%9E%E8%A7%A3%3A%CE%BCip) - 針對8/16位元微控制器之用的TCP/IP協定堆疊程式（繁體中文）
* [Internet History](http://www.livinginternet.com/i/ii.htm)（[页面存档备份](//web.archive.org/web/20000303225821/http://www.livinginternet.com/i/ii.htm)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [RFC 1122](https://datatracker.ietf.org/doc/html/rfc1122) - 因特网主机要求，通讯层
* Davies, Joseph; Lee, Thomas. [*Microsoft Windows server 2003 TCP/IP protocols and services : technical reference*](https://archive.org/details/microsoftwindows0000davi). Redmond: Microsoft Press. 2003. [ISBN 978-0-7356-1291-4](/wiki/Special:BookSources/978-0-7356-1291-4 "Special:BookSources/978-0-7356-1291-4").
* Hunt, Craig. *TCP/IP network administration: help for UNIX system administrators* 2. ed., [Nachdr.] Beijing Köln: O'Reilly. 1999. [ISBN 978-1-56592-322-5](/wiki/Special:BookSources/978-1-56592-322-5 "Special:BookSources/978-1-56592-322-5").
* Stevens, W. Richard. The protocols. *TCP/IP Illustrated* 31. print. Boston: Addison-Wesley. 2010. [ISBN 978-0-201-63346-7](/wiki/Special:BookSources/978-0-201-63346-7 "Special:BookSources/978-0-201-63346-7").

[分类](/wiki/Special:Categories "Special:Categories")：​

* [TCP/IP](/wiki/Category:TCP/IP "Category:TCP/IP")

隐藏分类：​

* [使用RFC魔术链接的页面](/wiki/Category:%E4%BD%BF%E7%94%A8RFC%E9%AD%94%E6%9C%AF%E9%93%BE%E6%8E%A5%E7%9A%84%E9%A1%B5%E9%9D%A2 "Category:使用RFC魔术链接的页面")
* [需要校對的頁面](/wiki/Category:%E9%9C%80%E8%A6%81%E6%A0%A1%E5%B0%8D%E7%9A%84%E9%A0%81%E9%9D%A2 "Category:需要校對的頁面")
* [含有美國英語的條目](/wiki/Category:%E5%90%AB%E6%9C%89%E7%BE%8E%E5%9C%8B%E8%8B%B1%E8%AA%9E%E7%9A%84%E6%A2%9D%E7%9B%AE "Category:含有美國英語的條目")
* [含有英語的條目](/wiki/Category:%E5%90%AB%E6%9C%89%E8%8B%B1%E8%AA%9E%E7%9A%84%E6%A2%9D%E7%9B%AE "Category:含有英語的條目")
