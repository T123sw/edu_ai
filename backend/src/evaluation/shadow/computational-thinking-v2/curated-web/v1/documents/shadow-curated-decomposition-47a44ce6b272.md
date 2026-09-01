# 关注点分离｜精选补充资料

> 来源：[维基百科（中文）](https://zh.wikipedia.org/wiki/%E5%85%B3%E6%B3%A8%E7%82%B9%E5%88%86%E7%A6%BB)  
> 许可：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)  
> 语言：简体中文  
> 获取时间：2026-08-08T09:43:26.918285+00:00

维基百科，自由的百科全书

在[計算機科學](/wiki/%E8%A8%88%E7%AE%97%E6%A9%9F%E7%A7%91%E5%AD%B8 "計算機科學")中，**關注點分離**（Separation of concerns，SoC），是將計算機程序分隔為不同部份的設計原則。每一部份會有各自的關注焦點。關注焦點是影響計算機程式程式碼的一組資訊。關注焦點可以像是將程式碼優化過的硬件細節一般，或者像實例化類別的名稱一樣具體。展現關注點分離設計的程序被稱為[模組化](/wiki/%E6%A8%A1%E5%9D%97%E5%8C%96%E7%BC%96%E7%A8%8B "模块化编程")程序。模組化程度，也就是區分關注焦點，通過將資訊[封装](/wiki/%E5%B0%81%E8%A3%9D_(%E7%89%A9%E4%BB%B6%E5%B0%8E%E5%90%91%E7%A8%8B%E5%BC%8F%E8%A8%AD%E8%A8%88) "封裝 (物件導向程式設計)")在具有明確界面的程序代碼段落中。封裝是一種[資訊隱藏](/wiki/%E8%B3%87%E8%A8%8A%E9%9A%B1%E8%97%8F_(%E9%9B%BB%E8%85%A6%E7%A7%91%E5%AD%B8) "資訊隱藏 (電腦科學)")手段。資訊系統中的分層設計是關注點分離的另一個實施例（例如，表示層，業務邏輯層，數據訪問層，持久數據層）。

关注点分离，是對只与「特定概念、目标」（[關注點](/wiki/%E9%97%9C%E6%B3%A8%E9%BB%9E "關注點")）相关联的[软件](/wiki/%E8%BD%AF%E4%BB%B6 "软件")组成部分進行「标识、[封装](/wiki/%E5%B0%81%E8%A3%9D_(%E7%89%A9%E4%BB%B6%E5%B0%8E%E5%90%91%E7%A8%8B%E5%BC%8F%E8%A8%AD%E8%A8%88) "封裝 (物件導向程式設計)")和操纵」的能力，即标识、封装和操纵关注点的能力。是处理复杂性的一个原则。由于关注点混杂在一起会导致复杂性大大增加，所以能够把不同的关注点分离开来，分别处理就是处理复杂性的一个原则，一种方法。分离关注点使得解决特定领域问题的程式碼从业务逻辑中独立出来，业务逻辑的程式碼中不再含有针对特定领域问题程式碼的调用（將针对特定领域问题程式碼抽象化成較少的程式碼，例如將程式碼封裝成function或是class），業務邏輯同特定领域问题的关系通过侧面来封装、维护，这样原本分散在整个[应用程序](/wiki/%E5%BA%94%E7%94%A8%E7%A8%8B%E5%BA%8F "应用程序")中的变动就可以很好的管理起来。

關注點分離的價值在於簡化計算機程序的開發和維護。當關注點分開時，各部份可以重複使用，以及獨立開發和更新。具有特殊價值的是能夠稍後改進或修改一段代碼，而無需知道其他部分的細節必須對這些部分進行相應的更改。

## 實作

編程語言提供的[物件導向設計](/wiki/%E7%89%A9%E4%BB%B6%E5%B0%8E%E5%90%91%E8%A8%AD%E8%A8%88 "物件導向設計")或[模块化编程](/wiki/%E6%A8%A1%E5%9D%97%E5%8C%96%E7%BC%96%E7%A8%8B "模块化编程")機制，就是允許開發人員提供SoC的機制。例如，C#，C++，Delphi和 Java等物件導向的編程語言可以將關注點分解為物件，像[MVC](/wiki/MVC "MVC")或[MVP](/wiki/Model-view-presenter "Model-view-presenter")這樣的架構設計模式，將內容從呈現和數據處理（模型）與內容分開（[呈现与内容分离](/wiki/%E5%91%88%E7%8E%B0%E4%B8%8E%E5%86%85%E5%AE%B9%E5%88%86%E7%A6%BB "呈现与内容分离")）。[服務導向](/w/index.php?title=%E6%9C%8D%E5%8B%99%E5%B0%8E%E5%90%91&action=edit&redlink=1 "服務導向（页面不存在）")（英语：[Service-orientation](https://en.wikipedia.org/wiki/Service-orientation "en:Service-orientation")）的設計可將關注點分解為[服務](/w/index.php?title=%E6%9C%8D%E5%8B%99_(%E7%B3%BB%E7%B5%B1%E6%9E%B6%E6%A7%8B)&action=edit&redlink=1 "服務 (系統架構)（页面不存在）")（英语：[Service (systems architecture)](https://en.wikipedia.org/wiki/Service_(systems_architecture) "en:Service (systems architecture)")）。諸如C和Pascal之類的程序式編程語言可將關注點分成[過程](/wiki/%E5%AD%90%E7%A8%8B%E5%BA%8F "子程序")或[函数](/wiki/%E5%87%BD%E6%95%B0_(%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A7%91%E5%AD%A6) "函数 (计算机科学)")。[面向切面編程](/wiki/%E9%9D%A2%E5%90%91%E5%88%87%E9%9D%A2%E7%BC%96%E7%A8%8B "面向切面编程")語言可以將關注點分解為[方面](/w/index.php?title=%E5%88%87%E9%9D%A2_(%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%BC%96%E7%A8%8B)&action=edit&redlink=1 "切面 (计算机编程)（页面不存在）")（英语：[Aspect (computer programming)](https://en.wikipedia.org/wiki/Aspect_(computer_programming) "en:Aspect (computer programming)")）和對象。

在許多其他領域，例如[城市規劃](/wiki/%E5%9F%8E%E5%B8%82%E8%A6%8F%E5%8A%83 "城市規劃")、[建築](/wiki/%E5%BB%BA%E7%AF%89 "建築")或[信息设计](/wiki/%E4%BF%A1%E6%81%AF%E8%AE%BE%E8%AE%A1 "信息设计")，分離關注點也是一個重要的設計原則。目標是更有效地理解，設計和管理許多功能相互依存的複雜系統，以便功能可以重用，獨立於其他功能進行優化，並且避免其他功能的潛在故障。常見的例子包括將一個空間分隔成多個房間，這樣一個房間的活動不會影響其他房間的人；或是配電將爐子保持在一個電路，而燈光則保持在另一個電路上，這樣爐子的超載就不會影響燈光。房間分隔的例子顯示了封裝，其中一個房間內的資訊（無論有多混亂）不會用於其他房間，除非通過界面（門是接口）。電路的例子表明，一個模組內部的活動是一個電力消費者附加的電路，不會影響不同模塊中的活動，因此每個模組不會額外去關注另一個模塊發生的情況。

## 起源

这个概念是1974年，[艾茲赫爾·戴克斯特拉](/wiki/%E8%89%BE%E5%85%B9%E8%B5%AB%E5%B0%94%C2%B7%E6%88%B4%E5%85%8B%E6%96%AF%E7%89%B9%E6%8B%89 "艾兹赫尔·戴克斯特拉")在他的文章《On the role of scientific thought》中提出的。

> 让我告诉你，对我来说所有聰明的思考的共通特性是什么。一个人要有系统地深入研究一门课题；必须將這們課題獨立出來，記住在任何時候都只能关注其中一个方面。 比如说，我们知道一个程式必须是正确的，因此我们可以只抓这个点来研究；我们同时也清楚它应当是高效率的，我们可以改天来研究它的效率，等等。我们也可以问自己，程式是否是可取的（desirable）？如果是，为什么？相反的，同时应对好幾個个方面不會得到任何結果！这就是我有时提到的「the separation of concerns（关注点分离）」。这个技巧就算不是完美可行的，也仍是我知道有效地组织思维的唯一可用技巧。这是就是我说的「将一个人的注意力集中在几个方面上」。这并不是说忽略其他方面，只是表明从这个方面来看，其他方面並无关紧要这一事实。这即是同时拥有单任务和多任务思维。

15年之后，这个概念已经被人们所接受。1989年，Chris Reade写的《Elements of Functional Programming》有这样的描述：

> 一个程式在執行的时候一定会同时做以下几件事情：
>
> 1. 描述所要解决的问题
> 2. 按照计算的顺序分成几个部分执行
> 3. 同时处理内存管理

Reade 接着说,

> 理想情况下，程序员应该只关注第一个問題（所要解决的问题），因为这个问题是更应该被关注。很明显的，我们可以通过解決重要的問題來得到更可靠的结果。
>
> 分离关注还有其它的好处。比如，程式可以分離内存管理和执行顺序。然后我们只去一步步的解决问题，不管机器的物理架构。当我们用高速平行的机器或者分布式系統的时候，只需要改动很小的一部分。
>
> 这就意味着编程语言的实现者必须在不同的机器和机制下，实现相关的功能。

## 例子

### 互聯網協議堆疊

关注点分离是網路設計中的重點。在[TCP/IP协议族](/wiki/TCP/IP%E5%8D%8F%E8%AE%AE%E6%97%8F "TCP/IP协议族")的設計時，有許多心力用在关注点分离，因此有良好定義的[OSI模型](/wiki/OSI%E6%A8%A1%E5%9E%8B "OSI模型")。這可以讓通訊協定的設計者專注在每一層的關注點，不考慮其他層的影響。例如應用層的協定，關注的是如何將郵件資料在可靠的傳送服務上傳輸的細節（一般會是[传输控制协议](/wiki/%E4%BC%A0%E8%BE%93%E6%8E%A7%E5%88%B6%E5%8D%8F%E8%AE%AE "传输控制协议")），不會關注传输控制协议旳細節。TCP不會關注資料封包的路由，路由是由[網路層](/wiki/%E7%B6%B2%E7%B5%A1%E5%B1%A4 "網絡層")處理的內容。

### HTML，CSS和JavaScript

[HTML](/wiki/HTML "HTML")、[层叠样式表](/wiki/%E5%B1%82%E5%8F%A0%E6%A0%B7%E5%BC%8F%E8%A1%A8 "层叠样式表")（CSS）和[JavaScript](/wiki/JavaScript "JavaScript")（JS）是開發網頁及相關服務時會用到的語言，彼此的機能是互補的。HTML主要是用在網站內容的結構、CSS是用在內容呈現方式的定義、JS定義網頁和用戶互動的方式，以及網頁的行為。以往的設計不是如此，在導入CSS之前，HTML同時要定義網頁的內容以及顯示方式。

### 主題導向的編程

[主題導向的編程](/w/index.php?title=%E4%B8%BB%E9%A1%8C%E5%B0%8E%E5%90%91%E7%9A%84%E7%B7%A8%E7%A8%8B&action=edit&redlink=1 "主題導向的編程（页面不存在）")（英语：[Subject-oriented programming](https://en.wikipedia.org/wiki/Subject-oriented_programming "en:Subject-oriented programming")）可以用分開的軟體結構來處理關注點分離，每一個關注點之間都是平等的。每一個關注點會有自己的類別結構，這些類別結構組成物件、也會提供狀態和方法給複合各關注點的結果。相依性關係會描述這些不同關注點中類別和方法，彼此之間的關係，讓許多關注點可以聯合產生複合式的行為。多維度关注点分离（Multi-dimensional Separation of Concerns）可以用多維「矩陣」的方式來進行各關注點之間的分析及複合，每一個關注點提供一個維度，上面會列舉各個點，其中的矩陣元素會有適當的軟件工件（software artifacts）。

### 面向切面的程序设计

[面向切面的程序设计](/wiki/%E9%9D%A2%E5%90%91%E5%88%87%E9%9D%A2%E7%9A%84%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1 "面向切面的程序设计")可以將[横切关注点](/wiki/%E6%A8%AA%E5%88%87%E5%85%B3%E6%B3%A8%E7%82%B9 "横切关注点")視為主要关注点進行處理。例如，大部份旳軟體都需要某程度的[安全性](/wiki/%E8%AE%A1%E7%AE%97%E6%9C%BA%E5%AE%89%E5%85%A8 "计算机安全")及[数据记录](/wiki/%E6%95%B0%E6%8D%AE%E8%AE%B0%E5%BD%95%E5%99%A8 "数据记录器")。安全性及数据记录一般會視為次要關注點，主要關注點一般是實現業務目標。不過在設計程式時，其安全性需要在一開始就考慮進來，而不是視為次要關注點。若在程式開發後再考慮安全性，多半會有安全模型不足的問題，會有很多後續被攻擊的風險。這可以用面向切面的程序设计來解決。例如，有一個切面可以寫成強制呼叫特定API時一定要记录，或是在丟出例外時，一定要記錄錯誤，不論哪一段程式的程式碼丟出錯誤或是傳播錯誤，都不會遺漏。

### 人工智能中的分析水準

在[认知科学](/wiki/%E8%AE%A4%E7%9F%A5%E7%A7%91%E5%AD%A6 "认知科学")及[人工智能](/wiki/%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD "人工智能")中，常常會用到[大卫·马尔](/wiki/%E5%A4%A7%E5%8D%AB%C2%B7%E9%A9%AC%E5%B0%94 "大卫·马尔")的levels of analysis。研究者可以專注在 (1)需要計算人工智慧的哪一個層面 (2)使用的演算法 (3)演算法在硬體中實現的情形。关注点分离類似軟體工程及硬體工程中的[介面](/wiki/%E4%BB%8B%E9%9D%A2_(%E8%B3%87%E8%A8%8A%E7%A7%91%E6%8A%80) "介面 (資訊科技)")/實現的差異。

### 規範化系統

在[規範化系統](/w/index.php?title=%E8%A6%8F%E7%AF%84%E5%8C%96%E7%B3%BB%E7%B5%B1&action=edit&redlink=1 "規範化系統（页面不存在）")（normalized system）中，关注点分离是四個指導原則之一。堅持此一原則可以減少組合性的效應。組合性的效應會在維護軟體時，漸漸的進入系統中。在規範化系統中，可以用工具積極的支持关注点分离。

### 关注点分离和部份類別

关注点分离可以用[部份類別](/w/index.php?title=%E9%83%A8%E4%BB%BD%E9%A1%9E%E5%88%A5&action=edit&redlink=1 "部份類別（页面不存在）")（英语：[partial class](https://en.wikipedia.org/wiki/partial_class "en:partial class")）的方式實現

#### 关注点分离和Ruby中的部份類別

bear\_hunting.rb

```
class Bear
  def hunt
    forest.select(&:food?)
  end
end
```

bear\_eating.rb

```
class Bear
  def eat(food)
    raise "#{food} is not edible!" unless food.respond_to? :nutrition_value
    food.nutrition_value
  end
end
```

bear\_hunger.rb

```
class Bear
  attr_accessor :hunger
  def monitor_hunger
    if hunger > 50
      food = hunt
      hunger -= eat(food)
    end
  end
end
```

## 相關條目

* [抽象原則 (程式設計)](/w/index.php?title=%E6%8A%BD%E8%B1%A1%E5%8E%9F%E5%89%87_(%E7%A8%8B%E5%BC%8F%E8%A8%AD%E8%A8%88)&action=edit&redlink=1 "抽象原則 (程式設計)（页面不存在）")（英语：[Abstraction principle (programming)](https://en.wikipedia.org/wiki/Abstraction_principle_(programming) "en:Abstraction principle (programming)")）
* [面向切面的程序设计](/wiki/%E9%9D%A2%E5%90%91%E5%88%87%E9%9D%A2%E7%9A%84%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1 "面向切面的程序设计")
* [關注點](/wiki/%E9%97%9C%E6%B3%A8%E9%BB%9E "關注點")
* [主关注点](/wiki/%E4%B8%BB%E5%85%B3%E6%B3%A8%E7%82%B9 "主关注点")
* [耦合性 (計算機科學)](/wiki/%E8%80%A6%E5%90%88%E6%80%A7_(%E8%A8%88%E7%AE%97%E6%A9%9F%E7%A7%91%E5%AD%B8) "耦合性 (計算機科學)")
* [横切关注点](/wiki/%E6%A8%AA%E5%88%87%E5%85%B3%E6%B3%A8%E7%82%B9 "横切关注点")
* [整全觀](/wiki/%E6%95%B4%E5%85%A8%E8%A7%80 "整全觀")
* [模組化設計](/wiki/%E6%A8%A1%E7%B5%84%E5%8C%96%E8%A8%AD%E8%A8%88 "模組化設計")
* [模块化编程](/wiki/%E6%A8%A1%E5%9D%97%E5%8C%96%E7%BC%96%E7%A8%8B "模块化编程")
* [呈现与内容分离](/wiki/%E5%91%88%E7%8E%B0%E4%B8%8E%E5%86%85%E5%AE%B9%E5%88%86%E7%A6%BB "呈现与内容分离")
* [单一功能原则](/wiki/%E5%8D%95%E4%B8%80%E5%8A%9F%E8%83%BD%E5%8E%9F%E5%88%99 "单一功能原则")
* [機制與策略分離](/w/index.php?title=%E6%A9%9F%E5%88%B6%E8%88%87%E7%AD%96%E7%95%A5%E5%88%86%E9%9B%A2&action=edit&redlink=1 "機制與策略分離（页面不存在）")（英语：[Separation of mechanism and policy](https://en.wikipedia.org/wiki/Separation_of_mechanism_and_policy "en:Separation of mechanism and policy")）
* [保護和安全分離](/w/index.php?title=%E4%BF%9D%E8%AD%B7%E5%92%8C%E5%AE%89%E5%85%A8%E5%88%86%E9%9B%A2&action=edit&redlink=1 "保護和安全分離（页面不存在）")（英语：[Separation of protection and security](https://en.wikipedia.org/wiki/Separation_of_protection_and_security "en:Separation of protection and security")）

## 參考資料

1. **[^](#cite_ref-laplante_1-0)** Laplante, Phillip. [What Every Engineer Should Know About Software Engineering](https://books.google.com/books?id=pFHYk0KWAEgC&q=%22separation+of+concerns%22&pg=PA85). CRC Press. 2007  [2020-12-16]. [ISBN 978-0849372285](/wiki/Special:BookSources/978-0849372285 "Special:BookSources/978-0849372285"). （原始内容[存档](https://web.archive.org/web/20210529055543/https://books.google.com/books?id=pFHYk0KWAEgC&q=%22separation+of+concerns%22&pg=PA85)于2021-05-29）.
2. **[^](#cite_ref-mitchell_2-0)** Mitchell, Dr. R. J. [Managing Complexity in Software Engineering](https://books.google.com/books?id=uXtHeZt8ZowC&q=%22separation+of+concerns%22&pg=PA5). IEE. 1990: 5  [2020-12-16]. [ISBN 0863411711](/wiki/Special:BookSources/0863411711 "Special:BookSources/0863411711"). （原始内容[存档](https://web.archive.org/web/20210531044919/https://books.google.com/books?id=uXtHeZt8ZowC&q=%22separation+of+concerns%22&pg=PA5)于2021-05-31）.
3. **[^](#cite_ref-microsoft_3-0)** [Microsoft Application Architecture Guide](https://books.google.com/books?id=D9on897Ep7AC&q=%22separation+of+concerns%22+%22layered+design%22&pg=PT54). Microsoft Press. 2009  [2020-12-16]. [ISBN 978-0-7356-2710-9](/wiki/Special:BookSources/978-0-7356-2710-9 "Special:BookSources/978-0-7356-2710-9"). （原始内容[存档](https://web.archive.org/web/20210529055525/https://books.google.com/books?id=D9on897Ep7AC&q=%22separation+of+concerns%22+%22layered+design%22&pg=PT54)于2021-05-29）.
4. **[^](#cite_ref-richard_4-0)** Painter, Robert Richard. Software Plans: Multi-Dimensional Fine-Grained Separation of Concerns. Penn State. [CiteSeerX 10.1.1.110.9227](//citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.110.9227) .
5. **[^](#cite_ref-5)** [Dijkstra, Edsger W](/wiki/Edsger_W._Dijkstra "Edsger W. Dijkstra"). [On the role of scientific thought](https://www.cs.utexas.edu/users/EWD/transcriptions/EWD04xx/EWD447.html). [Selected writings on Computing: A Personal Perspective](https://archive.org/details/selectedwritings0000dijk/page/60). New York, NY, USA: Springer-Verlag. 1982: [60–66](https://archive.org/details/selectedwritings0000dijk/page/60). [ISBN 0-387-90652-5](/wiki/Special:BookSources/0-387-90652-5 "Special:BookSources/0-387-90652-5").
6. **[^](#cite_ref-6)** Reade, Chris. [Elements of Functional Programming](https://archive.org/details/elementsoffuncti00read). Boston, MA, USA: Addison-Wesley Longman. 1989. [ISBN 0-201-12915-9](/wiki/Special:BookSources/0-201-12915-9 "Special:BookSources/0-201-12915-9").  含有內容需登入查看的頁面 ([link](/wiki/Category:%E5%90%AB%E6%9C%89%E5%85%A7%E5%AE%B9%E9%9C%80%E7%99%BB%E5%85%A5%E6%9F%A5%E7%9C%8B%E7%9A%84%E9%A0%81%E9%9D%A2 "Category:含有內容需登入查看的頁面"))
7. **[^](#cite_ref-7)** Jess Nielsen. [Building Secure Applications](http://jess.heidrun.dk/cv/BuildingSecureApp.pdf) (PDF). June 2006  [2012-02-08]. （原始内容[存档](https://web.archive.org/web/20160416074512/http://jess.heidrun.dk/cv/BuildingSecureApp.pdf) (PDF)于2016-04-16）.
8. **[^](#cite_ref-8)** Tiago Dias. [Hyper/Net: MDSoC Support for .NET](http://ptsoft.net/tdd/papers/TDIAS06_HyperNet__MDSOC_support_for_NET.pdf) (PDF). DSOA 2006. October 2006  [2007-09-25]. （原始内容[存档](https://web.archive.org/web/20161003124428/http://ptsoft.net/tdd/papers/TDIAS06_HyperNet__MDSOC_support_for_NET.pdf) (PDF)于2016-10-03）.

## 外部連結

* [Multi-Dimensional Separation of Concerns](http://domino.watson.ibm.com/library/cyberdig.nsf/1e4115aea78b6e7c85256b360066f0d4/5af350e4286e003985256766004ebe71?OpenDocument) （[页面存档备份](//web.archive.org/web/20160809005116/http://domino.watson.ibm.com/library/cyberdig.nsf/1e4115aea78b6e7c85256b360066f0d4/5af350e4286e003985256766004ebe71?OpenDocument)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [TAOSAD](http://trese.cs.utwente.nl/taosad/separation_of_concerns.htm) （[页面存档备份](//web.archive.org/web/20161219013600/http://trese.cs.utwente.nl/taosad/separation_of_concerns.htm)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）
* [Tutorial and Workshop on Aspect-Oriented Programming and Separation of Concerns](http://www.comp.lancs.ac.uk/computing/users/marash/aopws2001/) （[页面存档备份](//web.archive.org/web/20080516050058/http://www.comp.lancs.ac.uk/computing/users/marash/aopws2001/)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）

[分类](/wiki/Special:Categories "Special:Categories")：​

* [还原论](/wiki/Category:%E8%BF%98%E5%8E%9F%E8%AE%BA "Category:还原论")
* [编程原则](/wiki/Category:%E7%BC%96%E7%A8%8B%E5%8E%9F%E5%88%99 "Category:编程原则")

隐藏分类：​

* [含有內容需登入查看的頁面](/wiki/Category:%E5%90%AB%E6%9C%89%E5%85%A7%E5%AE%B9%E9%9C%80%E7%99%BB%E5%85%A5%E6%9F%A5%E7%9C%8B%E7%9A%84%E9%A0%81%E9%9D%A2 "Category:含有內容需登入查看的頁面")
