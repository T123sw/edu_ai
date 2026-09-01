# Introduction to Pandas

> 来源：[博洛尼亚大学 Digital Humanities and Digital Knowledge 课程团队](https://thinkcompute.github.io/17-pandas.html)  
> 许可：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)  
> 语言：英文补充资料  
> 版本：0c6a477bcdb50fd73b3b06d08a8f56324c86454f  
> 署名：改编自 Silvio Peroni、Ivan Heibi、Arcangelo Massari（2025）《Think and Compute: a Primer for Digital Humanists》，原作采用 CC BY 4.0。

# Introduction to Pandas

In this chapter, we will see the basics of one of the most useful and used tool in Data Science projects, i.e. Python Pandas.

## What is Pandas

[Pandas](https://pandas.pydata.org/) is a powerful tool developed for data analysis and data manipulation which is used in several Data Science projects due to its flexibility. It is accompanied by a great [user guide](https://pandas.pydata.org/docs/user_guide/index.html), [tutorials](https://pandas.pydata.org/docs/getting_started/intro_tutorials/), a [cookbook](https://pandas.pydata.org/docs/user_guide/cookbook.html), an [API documentation](https://pandas.pydata.org/docs/reference/index.html), other free books (e.g. [Python Data Science Handbook](https://jakevdp.github.io/PythonDataScienceHandbook/index.html)), and several articles on the topic (e.g. [those available](https://programminghistorian.org/en/lessons/?search=pandas) in [Programming Historian](https://programminghistorian.org)). 

The official website makes available a ["Getting started" guide](https://pandas.pydata.org/getting_started.html) to show how to install and use it. Anyway, you can install Pandas in your machine using the [pip command](https://pip.pypa.io/en/stable/) as follows:

```
pip install pandas
```

Among the various things, Pandas introduces two new classes of objects that are used to handle any kind of data in tabular form. They are the class `Series` and the class `DataFrame`, described in the following subsections.

### What is a Series

A [series](https://pandas.pydata.org/docs/user_guide/dsintro.html#series) is a one-dimensional array (i.e. it acts as a list) of objects of any data type (integers, strings, floating point numbers, Python objects, etc.). Each item in the series is indexed by a specific label (it can be an integer, a string, etc.), that can be used to access such an item. If no index is specified, the class `Series` will create such an index automatically using non-negative numbers (i.e. starting counting elements from 0). 

| <span style="color:red">*index (the label)*</span> | element (the value) |
|---|---|
| <span style="color:red">*0*</span> | Ron |
| <span style="color:red">*1*</span> | Hermione |
| <span style="color:red">*2*</span> | Harry |
| <span style="color:red">*3*</span> | Tom |
| <span style="color:red">*4*</span> | James |
| <span style="color:red">*5*</span> | Lily |
| <span style="color:red">*6*</span> | Severus |
| <span style="color:red">*7*</span> | Sirius |

A new series in Pandas can be created as follows:

```python
from pandas import Series

my_series = Series(["Ron", "Hermione", "Harry", "Tom", "James", "Lily", "Severus", "Sirius"])
print(my_series)
```

As you can see, by printing the series on screen you get several information. The first column defines the indexes used to label each element of the series, which are listed in the second column. Finally, there is an indication of which kind of object are included in the series. In particular, in Pandas, the `object` data type (i.e. `dtype`) is used to define series that are made of string or mixed type objects. 

There are, of course, [other data types](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dtypes.html) that can be used in series (and, sometimes, automatically inferred by Pandas). If you already know that all the values of a certain series belong to the same data type, e.g. string as in the example above, you can force Pandas to interpret them in such a way by specifying the data type with the input named parameter `dtype` in the constructor. For instance, to list all the values of the previous series as strings, the parameter `dtype` set to the value `string` must be specified. In addition, it is also possible to assign a name (i.e. a string) to the series, using the input named parameter `name`. The use of both `dtype` and `name` are shown as follows:

```python
my_series = Series(["Ron", "Hermione", "Harry", "Tom", "James", "Lily", "Severus", "Sirius"], 
                   dtype="string", name="given name")
print(my_series)
```

It is possible to use the slicing mechanism similar to what implemented in Python list (i.e. `<series>[<start>:<end>]` to create subseries on the fly – it works even when the index labels are not integers! In addition, one can use either the method `get` or, alternatively, the instruction `<series>[<index>]` (it is similar to that available in Python dictionaries), taking in input an index label, to retrieve the value at the input index, as show in the following excerpt:

```python
sub_series = my_series[1:6]
print("The new subseries is:")
print(sub_series)

print("\nThe element at index 5 of the new subseries is:")
print(sub_series[5])
```

While it may seem as a list, a series in Pandas has [several additional properties and methods](https://pandas.pydata.org/docs/reference/api/pandas.Series.html) that enable one to access and modify the item in the series in very different ways. Thus, it is more powerful than a simple Python list, and it is the basic structure adopted in the class described in the following section.

### What is a DataFrame

In Pandas, a [DataFrame](https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe) is a table. You can imagine it as a set of named series containing the same amount of elements, where each series defines a column of the table, and all the series share the same index labels (referring to the rows of the table).

| <span style="color:red">*index (label for rows)*</span> | column name 1 (a series) | column name 2 (another series) |
|---|---|---|
| <span style="color:red">*0*</span> | Ron | Wisley |
| <span style="color:red">*1*</span> | Hermione | Granger |
| <span style="color:red">*2*</span> | Harry | Potter |
| <span style="color:red">*3*</span> | Tom | Riddle |
| <span style="color:red">*4*</span> | James | Potter |
| <span style="color:red">*5*</span> | Lily | Potter |
| <span style="color:red">*6*</span> | Severus | Snape |
| <span style="color:red">*7*</span> | Sirius | Black |

A new data frame in Pandas can be created as follows:

```python
from pandas import DataFrame

my_dataframe = DataFrame({
    "given name" : my_series,
    "family name" : Series(
        ["Wisley", "Granger", "Potter", "Riddle", "Potter", "Potter", "Snape", "Black"], dtype="string")
})

print(my_dataframe)
```

In this case (but, please, remeber that it is not the only way to create a new data frame), we use as input a dictionary where each key defines a column name and the series associated to such a key contains the values of each cell in that column. Then we can access the various columns in the data frame using the same approach seen for series, i.e. `<dataframe>[<column name>]`, as shown in the following excerpt:

```python
family_name_column = my_dataframe["family name"]
print(family_name_column)
```

Selecting a column returns a series defining that column that share the column name and the indexes as specified in the data frame. Similarly, using the instruction `<dataframe>.loc[<index label>]`, that takes in input an index label, returns the series defining the row at that input index, as shown in the following example:

```python
third_row = my_dataframe.loc[2]
print(third_row)
```

As shown in the code above, it returns a series which has the column names of the original data frame as index labels of the series, the name as the index label of the data frame row selected, and the data type of the row derived from the various data types of the data frame columns.

Finally, as seen with the series, also data frame can be sliced (by rows) using the indentical approach introduced in the series. For instance, the following code shows how to create a new data frame taking a selection of the rows:

```python
print("The new subdataframe is:")
sub_dataframe = my_dataframe[1:6]
print(sub_dataframe)

print("\nThe row at index 2 of the new subdataframe is:")
print(sub_dataframe.loc[2])
```

Also a data frame in Pandas has [several additional properties and methods](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html) that enable one to access and modify the cells in the data frame.

## How to load data into Pandas

Pandas makes available [several functions](https://pandas.pydata.org/docs/user_guide/io.html) to load data stored in different formats. Indeed, there is a particular function that we can use to load data from CSV representations of tabular data (as those introduced in Chapter {ref}`15-what-is-a-datum.md`), i.e. the [function `read_csv`](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html).

The method `read_csv` takes in input a file path and returns a `DataFrame` representing such tabular data, as shown as follows:

```python
from pandas import read_csv

df_publications = read_csv("notebook/01-publications.csv")
print(df_publications)
```

As you can see in the code above, the `print` function does not provide an appropriate visualisation of the data frame in Jupyter Lab, mainly because the content of its columns is more extensive than the example before. In Jupyter, it is possible to have a good preview of a data frame by simply name the variable in a runnable code, as follows:

```python
df_publications
```

By looking at the data frame, it appears clear that there is something odd in the data types shown, in particular in the columns `issue` and `volume`. In these columns there are two main issues. The first one concerns the data types associated to the column. Indeed, it seems that Pandas has interpreted automatically these columns as floating numbers, while they should be made of strings! This can be conformed by printing the data type (attribute `dtype`) associated to one of these columns, for instance:

```python
print(df_publications["issue"].dtype)
```

The other issue concerns that strange value in the last row, i.e. `NaN`. This special object is used when there is a [missing data](https://pandas.pydata.org/pandas-docs/stable/user_guide/missing_data.html) in a cell. However, once may expect that, since in the example we are dealing with string, we should simply use an empty string to represent such a missing data instead that such special object. 

In order to avoid this behaviour, it may be neccessary to use the method `read_csv` specifying an additional input named parameter, i.e. `dtype`, which enables the specification of a dictionary where the keys are column names, while the values are the strings representing the data type for each column. Instead, to force Pandas to use an empty string as default for string-based column in case of missing values, it is enough to tell the function `read_csv` not to use the default `NaN` for missing value by setting the input named parameter `keep_default_na` to `False`.

The following code shows how to specify such parameters, showing on screen how the new data frame has been modified:

```python
df_publications = read_csv("notebook/01-publications.csv", 
                           keep_default_na=False,
                           dtype={
                               "doi": "string",
                               "title": "string",
                               "publication year": "int",
                               "publication venue": "string",
                               "type": "string",
                               "issue": "string",
                               "volume": "string"
                           })
df_publications
```

## Iterating over a DataFrame and a Series

Being a table, there are two possible strategies for iterating over a `DataFrame` object: row iteration and column iteration. These two can be achieved by means of two distinct methods of the class `DataFrame`: the [method `iterrows`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.iterrows.html) and the [method `items`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.items.html).

The method `iterrows` is used to retrieve a list-like structure where each item has two elements: the index label and a series representing the row related to that index.

```python
for idx, row in df_publications.iterrows():
    print("\nThe index of the current row is", idx)
    print("The content of the row is as follows:")
    print(row)
```

If one wants to iterate also over a series representing a row, keeping track of the index labels of the series representing the row (i.e. the column names), one can use the [method `items`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.Series.items.html#pandas.Series.items) of the class `Series`:

```python
for row_idx, row in df_publications.iterrows():
    print("\nRow index", row_idx)
    for item_idx, item in row.items():
        print(item_idx, "-->", item)
```

The method `items` of the class `DataFrame` is used to retrieve a list-like structure where each item has two elements: the column name and a series representing the related column, as shown in the following excerpt:

```python
for column_name, column in df_publications.items():
    print("\nThe name of the current column is", column_name)
    print("The content of the column is as follows:")
    print(column)
```

## How to store data with Pandas

Pandas makes available a specific method (i.e. `to_csv`) to its main classes, i.e. `Series` and `DataFrame`, to enable one to store them in the filesystem. In the `DataFrame` class, the [method `to_csv`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html) takes in input the file path where to store the CSV file representing the data frame as shown as follows:

```python
df_publications.to_csv("notebook/03-publications.csv")
```

However, the method `to_csv` called as shown above will store also an additional column at the beginning, i.e. that related with the index labels for each row. In order to avoid to preserve the index, it is possible to set the input named parameter `index` to `False`, as shown in the following excerpt:

```python
df_publications.to_csv("notebook/03-publications_no_index.csv", index=False)
```

## Main operations with DataFrame

Pandas makes available several operations for [indexing, selecting](https://pandas.pydata.org/docs/user_guide/indexing.html), [merging, joining, concatenating, and comparing](https://pandas.pydata.org/docs/user_guide/merging.html) data in a data frame. In the following section, we introduce two of them, but several additional operations are available in the documentation linked above.

### Querying

Pandas has several ways enabling querying a data frame and returning a selections of its rows. Among the various methods, one extremely useful is the [method `query`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.query.html), that takes in input a string representing an expression for querying the data frame and returns a new data frame compliant with the query.

The expression can be a [combination of boolean expressions and comparisons](https://pandas.pydata.org/docs/user_guide/indexing.html#the-query-method), that enable to filter rows according to the values of its cells. For instance, to get all the rows that are journal articles, one can run the following query:

```python
df_publications.query("type == 'journal article'")
```

In case we want to refer to columns with spaces, we must use the tick character (i.e. <code>`</code>) to enclose the name of the column. For instance, to get all the rows that have a publication date lesser than <code>2003</code>, we can run the following query:

```python
df_publications.query("`publication year` < 2003")
```

It is also possible to combine queries by using the boolean operators `and` and `or`. For instance, to get all the journal articles published before 2003, we can run the following query:

```python
df_publications.query("type == 'journal article' and `publication year` < 2003")
```

### Joining

Joining two data frames into a new one according to some common value is a crucial operation to enable to answer more complex query, such as getting all the articles published in the journal named *Current Opinion in Chemical Biology*. Indeed, the data frame about publications we have considered so fare does not have any information about the name of the venues, nor their types. However, considering the data we used in the first tutorial, we know that such information is actually included in another CSV file entirely dedicated to venues, that we can load in pandas as follows:

```python
df_venues = read_csv("notebook/01-venues.csv", 
                     keep_default_na=False,
                     dtype={
                         "id": "string",
                         "name": "string",
                         "type": "string"
                     })
df_venues  # draw the table in the notebook
```

Thus, in order to run such a query, first we should ask to this new data frame which is the `id` associated to the journal named *Current Openion in Chemical Biology*, and then to ask the other data frame with publications to retrieve all the rows that have such an identifier as `publication venue`.

However, in Pandas this can be done in just one query if we join before the two data frames in a new one containing a combination of the two tables. Indeed, as you can obsever, the data frame of publications and that of venues share some values in common. Indeed, as mentioned above, the values specified in the `publication venue` column in the publications data frame recall those specified in the `id` column of the venue data frame. Thus, in principle, it is possible to join these two tables by considering that common values. 

Pandas provides the [function `merge`](https://pandas.pydata.org/docs/user_guide/merging.html#database-style-dataframe-or-named-series-joining-merging) to perform such an operation. Among the various input parameters such a function can take in input, those we use in this example to join these two data frames are the data frames them self and the name of the columns in the first (named *left*) data frame and the second (named *right*) data frame to use for joining, specified by using the input named parameters `left_on` and `right_on` respectively, as shown in the following excerpt:

```python
from pandas import merge

df_joined = merge(df_publications, df_venues, left_on="publication venue", right_on="id")
df_joined  # draw the table in the notebook
```

As you can see from the data frame above, all the rows of the publications data frame (the *left* data frame of the join) have been extended using the values specified in the venues data frame (the *right* data frame of the join) mapping the values in the columns `publication year` (in *left*) and `id` (in *right*). In addition, Pandas modifies the name of the columns that have the same name in both data frames of the join – indeed the columns `type` became `type_x` (refferring to *left*) and `type_y` (referring to *right*).

Having this new data frame, the original query we wanted to run becomes pretty easy to define:

```python
df_joined.query("type_y == 'journal' and name == 'Current Opinion in Chemical Biology'")
```
