# 可计算性理论｜精选补充资料

> 来源：[维基百科（中文）](https://zh.wikipedia.org/wiki/%E5%8F%AF%E8%AE%A1%E7%AE%97%E6%80%A7%E7%90%86%E8%AE%BA)  
> 许可：[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)  
> 语言：简体中文  
> 获取时间：2026-08-08T09:43:37.350322+00:00

维基百科，自由的百科全书

关于对于数理逻辑中的可计算性理论，请见「**[递归论](/wiki/%E9%80%92%E5%BD%92%E8%AE%BA "递归论")**」。

在[计算机科学](/wiki/%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A7%91%E5%AD%A6 "计算机科学")中，**可计算性理论**（Computability theory）作为[计算理论](/wiki/%E8%AE%A1%E7%AE%97%E7%90%86%E8%AE%BA "计算理论")的一个分支，研究在不同的[计算模型](/wiki/%E8%AE%A1%E7%AE%97%E6%A8%A1%E5%9E%8B "计算模型")下哪些[算法](/wiki/%E7%AE%97%E6%B3%95 "算法")问题能够被解决。相对应的，计算理论的另一块主要内容，[计算复杂性理论](/wiki/%E8%AE%A1%E7%AE%97%E5%A4%8D%E6%9D%82%E6%80%A7%E7%90%86%E8%AE%BA "计算复杂性理论")考虑一个问题怎样才能被*有效的*解决。

## 历史与递归论的联系

## 计算模型

[图灵机](/wiki/%E5%9B%BE%E7%81%B5%E6%9C%BA "图灵机")和[邱奇－图灵论题](/wiki/%E9%82%B1%E5%A5%87%EF%BC%8D%E5%9B%BE%E7%81%B5%E8%AE%BA%E9%A2%98 "邱奇－图灵论题")

## 图灵机的可计算性理论

我们考虑关于图灵机的可计算性理论。本节中，固定字符集是{0, 1}，



{
0
,
1

}

∗
{\displaystyle \{0,1\}^{\*}}
${\displaystyle \{0,1\}^{\*}}$是所有有限长度字符串的集合。一个语言即是



{
0
,
1

}

∗
{\displaystyle \{0,1\}^{\*}}
${\displaystyle \{0,1\}^{\*}}$的一个子集。

一个语言L是可以被图灵机所枚举的，如果存在一个图灵机



M
{\displaystyle M}
${\displaystyle M}$，使得输入是



L
{\displaystyle L}
${\displaystyle L}$中的串时，



M
{\displaystyle M}
${\displaystyle M}$输出“接受”；而对非



L
{\displaystyle L}
${\displaystyle L}$中的串，



M
{\displaystyle M}
${\displaystyle M}$输出“拒绝”或**不停机**。而一个语言




L
′
{\displaystyle L'}
${\displaystyle L'}$是可以被图灵机所[判定](/wiki/%E5%8F%AF%E5%88%A4%E5%AE%9A%E6%80%A7 "可判定性")的，如果存在一个图灵机




M
′
{\displaystyle M'}
${\displaystyle M'}$，使得输入是



L
{\displaystyle L}
${\displaystyle L}$中的串时，




M
′
{\displaystyle M'}
${\displaystyle M'}$输出“接受”；而对非



L
{\displaystyle L}
${\displaystyle L}$中的串，




M
′
{\displaystyle M'}
${\displaystyle M'}$输出“拒绝”。注意这里的区别在于，对于图灵机可判定的语言，我们需要在所有输出上，该图灵机都要停机。

### 可计算性等级

这样我们可以定义可计算性等级：所有的语言的集合，记为



A
l
l
{\displaystyle All}
${\displaystyle All}$；递归可枚举语言，即可以被图灵机枚举的语言的集合，记为



R
E
{\displaystyle RE}
${\displaystyle RE}$；递归语言，即可以被图灵机判定的语言的集合，记为



R
{\displaystyle R}
${\displaystyle R}$。可见



R
⊆
R
E
⊆
A
l
l
{\displaystyle R\subseteq RE\subseteq All}
${\displaystyle R\subseteq RE\subseteq All}$，即形成**可计算性等级**。那么产生相关的问题即是两个包含关系是不是严格的，即是否有在



A
l
l
{\displaystyle All}
${\displaystyle All}$而不在



R
E
{\displaystyle RE}
${\displaystyle RE}$中的语言，以及在



R
E
{\displaystyle RE}
${\displaystyle RE}$而不在



R
{\displaystyle R}
${\displaystyle R}$中的语言。[阿兰·图灵](/wiki/%E9%98%BF%E5%85%B0%C2%B7%E5%9B%BE%E7%81%B5 "阿兰·图灵")在1930年代的工作表明这两个包含关系都是严格的，即可以证明存在语言




L

d
{\displaystyle L\_{d}}
${\displaystyle L\_{d}}$，是不能被图灵机所枚举的，以及存在语言




L

u
{\displaystyle L\_{u}}
${\displaystyle L\_{u}}$，是不能被图灵机所判定的。证明的主要思想是[對角論證法](/wiki/%E5%B0%8D%E8%A7%92%E8%AB%96%E8%AD%89%E6%B3%95 "對角論證法")。

### 停机问题

停机问题就是判断任意一个程序是否会在有限的时间之内结束运行的问题。该问题等价于如下的判定问题：给定一个程序P和输入w，程序P在输入w下是否能够最终停止。

### PCP问题

[波斯特对应问题](/wiki/%E6%B3%A2%E6%96%AF%E7%89%B9%E5%AF%B9%E5%BA%94%E9%97%AE%E9%A2%98 "波斯特对应问题")（Post's correspondence problem）。

### 不可解度

[不可解度](/wiki/%E4%B8%8D%E5%8F%AF%E8%A7%A3%E5%BA%A6 "不可解度")的概念定义了不可解的集合之间的相对计算难度。例如，不可解的停机问题显然比任何可解的集合都要难，然而同样不可解的“元停机问题”（即所有具备停机问题的[预言机](/wiki/%E9%A2%84%E8%A8%80%E6%9C%BA "预言机")的停机问题）却要难过停机问题，因为具备元停机问题的预言机可以解出停机问题，然而具备停机问题的预言机却不能解出元停机问题。

## 更强的模型

### 带神谕的图灵机（[预言机](/wiki/%E9%A2%84%E8%A8%80%E6%9C%BA "预言机")）

## 定理

* [波斯特定理](/wiki/%E6%B3%A2%E6%96%AF%E7%89%B9%E5%AF%B9%E5%BA%94%E9%97%AE%E9%A2%98 "波斯特对应问题")
* [克莱尼–波斯特定理](/wiki/%E5%85%8B%E8%8E%B1%E5%B0%BC%E2%80%93%E6%B3%A2%E6%96%AF%E7%89%B9%E5%AE%9A%E7%90%86 "克莱尼–波斯特定理")
* [弗里德堡–穆奇尼克定理](/wiki/%E5%BC%97%E9%87%8C%E5%BE%B7%E5%A0%A1%E2%80%93%E7%A9%86%E5%A5%87%E5%B0%BC%E5%85%8B%E5%AE%9A%E7%90%86 "弗里德堡–穆奇尼克定理")
* [波斯纳–罗宾逊定理](/wiki/%E6%B3%A2%E6%96%AF%E7%BA%B3%E2%80%93%E7%BD%97%E5%AE%BE%E9%80%8A%E5%AE%9A%E7%90%86 "波斯纳–罗宾逊定理")
* [跳躍逆轉定理](/wiki/%E8%B7%B3%E8%B7%83%E9%80%86%E8%BD%AC%E5%AE%9A%E7%90%86 "跳跃逆转定理")

* [可计算性理论](http://www1.chkd.cnki.net/kns50/XSearch.aspx?KeyWord=%E5%8F%AF%E8%AE%A1%E7%AE%97%E6%80%A7%E7%90%86%E8%AE%BA)[[永久失效連結](/wiki/Wikipedia:%E5%A4%B1%E6%95%88%E9%93%BE%E6%8E%A5 "Wikipedia:失效链接")]

[分类](/wiki/Special:Categories "Special:Categories")：​

* [計算理論](/wiki/Category:%E8%A8%88%E7%AE%97%E7%90%86%E8%AB%96 "Category:計算理論")

隐藏分类：​

* [自2017年12月带有失效链接的条目](/wiki/Category:%E8%87%AA2017%E5%B9%B412%E6%9C%88%E5%B8%A6%E6%9C%89%E5%A4%B1%E6%95%88%E9%93%BE%E6%8E%A5%E7%9A%84%E6%9D%A1%E7%9B%AE "Category:自2017年12月带有失效链接的条目")
* [条目有永久失效的外部链接](/wiki/Category:%E6%9D%A1%E7%9B%AE%E6%9C%89%E6%B0%B8%E4%B9%85%E5%A4%B1%E6%95%88%E7%9A%84%E5%A4%96%E9%83%A8%E9%93%BE%E6%8E%A5 "Category:条目有永久失效的外部链接")
