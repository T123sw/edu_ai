# 计算模型｜精选补充资料

> 来源：[维基百科（中文）](https://zh.wikipedia.org/wiki/%E8%AE%A1%E7%AE%97%E6%A8%A1%E5%9E%8B_(%E6%95%B0%E5%AD%A6))  
> 许可：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)  
> 语言：简体中文  
> 获取时间：2026-08-08T09:43:54.204226+00:00

维基百科，自由的百科全书

关于以计算机模型模拟复杂系统，请见「**[计算模型](/wiki/%E8%AE%A1%E7%AE%97%E6%A8%A1%E5%9E%8B "计算模型")**」。

在[可计算性理论](/wiki/%E5%8F%AF%E8%AE%A1%E7%AE%97%E6%80%A7%E7%90%86%E8%AE%BA "可计算性理论")和[计算复杂性理论](/wiki/%E8%AE%A1%E7%AE%97%E5%A4%8D%E6%9D%82%E6%80%A7%E7%90%86%E8%AE%BA "计算复杂性理论")中，**计算模型**（**model of computation**）描述了如何根据一组输入值计算[函数](/wiki/%E5%87%BD%E6%95%B0 "函数")的输出，包含了负责运算、存储和通讯等结构的具体组织方式。它可以用于测量[算法](/wiki/%E7%AE%97%E6%B3%95 "算法")的[计算复杂度](/wiki/%E8%AE%A1%E7%AE%97%E5%A4%8D%E6%9D%82%E5%BA%A6 "计算复杂度")，总结出算法的性能，而不受特定技术和[实现](/wiki/%E5%AE%9E%E7%8E%B0 "实现")方式的性能差异所误导。

## 模型

计算模型可分为三大类：顺序模型、函数式模型以及同步模型。

### 顺序模型

顺序模型包括

* [图灵机](/wiki/%E5%9B%BE%E7%81%B5%E6%9C%BA "图灵机")
* [有限状态机](/wiki/%E6%9C%89%E9%99%90%E7%8A%B6%E6%80%81%E6%9C%BA "有限状态机")
* [下推自动机](/wiki/%E4%B8%8B%E6%8E%A8%E8%87%AA%E5%8A%A8%E6%9C%BA "下推自动机")

### 函数式模型

函数式模型包括

* [递归函数](/wiki/%E9%80%92%E5%BD%92%E5%87%BD%E6%95%B0 "递归函数")
* [Λ演算](/wiki/%CE%9B%E6%BC%94%E7%AE%97 "Λ演算")
* [组合子逻辑](/wiki/%E7%BB%84%E5%90%88%E5%AD%90%E9%80%BB%E8%BE%91 "组合子逻辑")
* [細胞自動機](/wiki/%E7%B4%B0%E8%83%9E%E8%87%AA%E5%8B%95%E6%A9%9F "細胞自動機")
* [抽象重写系统](/w/index.php?title=%E6%8A%BD%E8%B1%A1%E9%87%8D%E5%86%99%E7%B3%BB%E7%BB%9F&action=edit&redlink=1 "抽象重写系统（页面不存在）")（英语：[Abstract rewriting system](https://en.wikipedia.org/wiki/Abstract_rewriting_system "en:Abstract rewriting system")）

### 同步模型

同步模型包括

* [演员模型](/wiki/%E6%BC%94%E5%91%98%E6%A8%A1%E5%9E%8B "演员模型")

各模型的表现不盡相同；例如，有限状态机可以计算的函数，图灵机也可以计算，反之则不然。

## 使用

在[算法分析](/wiki/%E7%AE%97%E6%B3%95%E5%88%86%E6%9E%90 "算法分析")领域，定义一个计算模型通常用具有单位成本的原始操作（也称**单位成本操作**）。一个常见例子是[随机存取机器](/wiki/%E9%9A%A8%E6%A9%9F%E5%AD%98%E5%8F%96%E6%A9%9F%E5%99%A8 "隨機存取機器")，任何存储单元的读写访问，都有着单位成本。在这方面，它与图灵机模型不同。

在[模型驱动工程](/wiki/%E6%A8%A1%E5%9E%8B%E9%A9%B1%E5%8A%A8%E5%B7%A5%E7%A8%8B "模型驱动工程")中，计算模型解释了整个系统的行为是如何由每个组件的行为所共同造成的。

一个经常被忽略的关键点是，一些已知计算复杂度下限的问题是由较为局限的运算集得出的，实践中可使用的运算集可能更加广泛而强大，因而一些算法的实际性能，可能比高度抽象的计算模型得出的结果要好。

## 分类

计算模型有很多，它们在各自容许的运算集和计算成本方面不同。它们可以被分为几大类：[抽象機器](/wiki/%E6%8A%BD%E8%B1%A1%E6%A9%9F%E5%99%A8 "抽象機器")和与其等同的模型（例如[Λ演算](/wiki/%CE%9B%E6%BC%94%E7%AE%97 "Λ演算")相当于[图灵机](/wiki/%E5%9B%BE%E7%81%B5%E6%9C%BA "图灵机")），用于可计算性、算法计算复杂性上限的证明；还有[决策树模型](/w/index.php?title=%E5%86%B3%E7%AD%96%E6%A0%91%E6%A8%A1%E5%9E%8B&action=edit&redlink=1 "决策树模型（页面不存在）")（英语：[Decision tree model](https://en.wikipedia.org/wiki/Decision_tree_model "en:Decision tree model")），用于证明算法问题计算复杂度的下限。

* [堆疊結構機器](/wiki/%E5%A0%86%E7%96%8A%E7%B5%90%E6%A7%8B%E6%A9%9F%E5%99%A8 "堆疊結構機器")（零操作数机器）
* [累加器](/wiki/%E7%B4%AF%E5%8A%A0%E5%99%A8 "累加器")（一操作数机器）
* [寄存器机](/wiki/%E5%AF%84%E5%AD%98%E5%99%A8%E6%9C%BA "寄存器机")（二、三、…操作数机器）
* [隨機存取機器](/wiki/%E9%9A%A8%E6%A9%9F%E5%AD%98%E5%8F%96%E6%A9%9F%E5%99%A8 "隨機存取機器")
* [细胞探针模型](/w/index.php?title=%E7%BB%86%E8%83%9E%E6%8E%A2%E9%92%88%E6%A8%A1%E5%9E%8B&action=edit&redlink=1 "细胞探针模型（页面不存在）")（英语：[Cell-probe model](https://en.wikipedia.org/wiki/Cell-probe_model "en:Cell-probe model")）

1. **[^](#cite_ref-1)** [计算模型](https://cs.brown.edu/people/jsavage/book/pdfs/ModelsOfComputation.pdf) (PDF).  [2024-01-09]. （原始内容[存档](https://web.archive.org/web/20240329142351/https://cs.brown.edu/people/jsavage/book/pdfs/ModelsOfComputation.pdf) (PDF)于2024-03-29）.
2. **[^](#cite_ref-2)** [Examples of the price of abstraction?](http://cstheory.stackexchange.com/questions/608/examples-of-the-price-of-abstraction) （[页面存档备份](//web.archive.org/web/20101125005845/http://cstheory.stackexchange.com/questions/608/examples-of-the-price-of-abstraction)，存于[互联网档案馆](/wiki/%E4%BA%92%E8%81%94%E7%BD%91%E6%A1%A3%E6%A1%88%E9%A6%86 "互联网档案馆")）, cstheory.stackexchange.com

* [Fernández, Maribel](/w/index.php?title=Maribel_Fern%C3%A1ndez&action=edit&redlink=1 "Maribel Fernández（页面不存在）"). Models of Computation: An Introduction to Computability Theory. Undergraduate Topics in Computer Science. Springer. 2009. [ISBN 978-1-84882-433-1](/wiki/Special:BookSources/978-1-84882-433-1 "Special:BookSources/978-1-84882-433-1").
* [Savage, John E.](/w/index.php?title=John_E._Savage&action=edit&redlink=1 "John E. Savage（页面不存在）") [Models Of Computation: Exploring the Power of Computing](https://web.archive.org/web/20161012145726/http://cs.brown.edu/~jes/book/home.html). 1998  [2016-12-23]. （[原始内容](http://www.cs.brown.edu/~jes/book/home.html)存档于2016-10-12）.

[分类](/wiki/Special:Categories "Special:Categories")：​

* [计算模型](/wiki/Category:%E8%AE%A1%E7%AE%97%E6%A8%A1%E5%9E%8B "Category:计算模型")
* [計算理論](/wiki/Category:%E8%A8%88%E7%AE%97%E7%90%86%E8%AB%96 "Category:計算理論")

隐藏分类：​

* [需要校對的翻譯頁面](/wiki/Category:%E9%9C%80%E8%A6%81%E6%A0%A1%E5%B0%8D%E7%9A%84%E7%BF%BB%E8%AD%AF%E9%A0%81%E9%9D%A2 "Category:需要校對的翻譯頁面")
* [所有需要專家關注的頁面](/wiki/Category:%E6%89%80%E6%9C%89%E9%9C%80%E8%A6%81%E5%B0%88%E5%AE%B6%E9%97%9C%E6%B3%A8%E7%9A%84%E9%A0%81%E9%9D%A2 "Category:所有需要專家關注的頁面")
* [其他需要專家關注的頁面](/wiki/Category:%E5%85%B6%E4%BB%96%E9%9C%80%E8%A6%81%E5%B0%88%E5%AE%B6%E9%97%9C%E6%B3%A8%E7%9A%84%E9%A0%81%E9%9D%A2 "Category:其他需要專家關注的頁面")
