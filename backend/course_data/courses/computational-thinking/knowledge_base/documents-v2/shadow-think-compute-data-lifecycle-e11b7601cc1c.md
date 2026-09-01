# Data formats and methods for storing data in Python

> 来源：[博洛尼亚大学 Digital Humanities and Digital Knowledge 课程团队](https://thinkcompute.github.io/15-what-is-a-datum.html)  
> 许可：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)  
> 语言：英文补充资料  
> 版本：0c6a477bcdb50fd73b3b06d08a8f56324c86454f  
> 署名：改编自 Silvio Peroni、Ivan Heibi、Arcangelo Massari（2025）《Think and Compute: a Primer for Digital Humanists》，原作采用 CC BY 4.0。

# Data formats and methods for storing data in Python

In this chapter, we see two basic formats to deal with data in Python: CSV and JSON.

## Comma-separated values (CSV)

The first and simplest format you can use to store and load data in Python is the [Comma-Separated Values (CSV)](https://en.wikipedia.org/wiki/Comma-separated_values). In practice, each CSV file defines a table of a fixed number of columns where each row represents a (subject) entity and each cell defines the (object) value associated to that entity via the predicate defined by the column label, if specified. While it is not mandatory to specify column labels, it makes a CSV file more understandable to humans and machines. These labels can be specified using the first row of a CSV, defining an header of the table represented. An example of a table represented with a CSV is shown as follows.

|   | column<sub>1</sub> | column<sub>2</sub>  | ... | column<sub>n</sub> |
|---|---|---|---|---|
| <span style="color: red">*entity<sub>1</sub>*</span> | value<sub>1</sub> | value<sub>1</sub> | ... | value<sub>n</sub> |
| <span style="color: red">*entity<sub>2</sub>*</span> | value<sub>1</sub> | value<sub>1</sub> | ... | value<sub>n</sub> |
| <span style="color: red">...</span> | ... | ... | ... | ... |
| <span style="color: red">*entity<sub>m</sub>*</span> | value<sub>1</sub> | value<sub>1</sub> | ... | value<sub>n</sub> |

Each cell in a row is defined by splitting the cell values using a comma (`,`). In case the comma is part of the value of a cell, it is possible to escape such a comma by putting the cell value between quotes (`"`). Finally, in case a cell value is defined using quotes and one or more quote is included in cell value, these must be escaped by using double quotes (`""`). The following table and the related CSV source show how to define in CSV cell values when these situations happen.

| column name | another name, with a comma |
|---|---|
| a value | a value, with a comma |
| a quoted "value" | a quoted "value", with a comma |

CSV <a href="01-example.csv">source</a>:

```
column name,"another name, with a comma"
a value,"a value, with a comma"
a quoted "value","a quoted ""value"", with a comma"
```

Python has a dedicated library to handle this format called [*csv*](https://docs.python.org/3/library/csv.html). In order to understand how to use it, we can start analysing two very simple CSV files, one containing [publications and some of their basic metadata](01-publications.csv) and another with [information about the venues](01-venues.csv) where such publications have been published. To open it as a source file, you can right-click on it in the left panel and select *Open With -> Editor*.

### Opening a CSV file

In order to understand how these files are represented in Python, let us try to load one of it into a Python object using the funcion *reader* included in the module *csv* mentioned above. For doing that, it is necessary to obtain a [file object](https://docs.python.org/3/glossary.html#term-file-object) of a particular file using the built-in [function `open` used with a `with` statement](https://docs.python.org/3/tutorial/inputoutput.html#reading-and-writing-files) as shown in the following excerpt:

```python
from csv import reader

with open("notebook/01-publications.csv", "r", encoding="utf-8") as f:
    publications = reader(f)
```

The function `open` takes in input several parameters and returns a file object, i.e. a Python object used to interact with a file stored in the file system. However, it is highly suggested to use at least the three specified above, that are:

1. the first positional parameter must contain the path of the file one wants to open;
2. the second positional parameter is the mode used to open the file (`"r"` stands for read, `"w"` for write, etc.);
3. the named parameter `encoding` specifying the encoding to open the file (`"utf-8"` must be used, if you do not want to have issues).

In addition, all file objects one wants to create in Python to process files stored in the file system must be also closed once all the operations on that file are concluded. The keyword `with` used with the function `open` allows one to handle the opening and closing of the file object automatically. In practice, once all the operation within the `with` block are executed, the related file object will be closed. Finally, the file object openned using the function `open` will be assigned to the variable that follows the keyword `as`, i.e. `f` in the example above. It is worth mentioning that the example just shown introduces how to open, in reading mode, any file in the file system, not only CSV files.

### CSV reader

Once our file object has been defined, we can read its content interpreting it as a CSV document using the [constructor `reader`](https://docs.python.org/3/library/csv.html#csv.reader) included in the package `csv`, which is imported by means of the usual command:

```
from csv import reader
```

The constructor `reader` takes in input a file object and returns an object of type (i.e. class) `_csv.reader`, that enables one to iterate over the CSV document row by row. To check the actual type, you can use the built-in function `type` passing the object as input, and then printing it on screen using either the function `print` or, when we want to print a complex structure, the [function `pprint`](https://docs.python.org/3/library/pprint.html#pprint.pprint) from the package `pprint` (a.k.a. *pretty print*), as shown running the following code:

```python
from pprint import pprint

pprint(type(publications))
```

An object of the class `_csv.reader` behaves like a list, and can be iterated using a for earch loop, as shown as follows:

```python
with open("notebook/01-publications.csv", "r", encoding="utf-8") as f:
    publications = reader(f)

    for row in publications:
        pprint(row)
```

In case you want to skip the header of the table if present, starting to look at the values directly, you need to use the built-in [function `next`](https://docs.python.org/3/library/functions.html#next) that takes in input any [iterator-based object](https://docs.python.org/3/glossary.html#term-iterator), such as our CSV reader, and skips to the next line:

```python
with open("notebook/01-publications.csv", "r", encoding="utf-8") as f:
    publications = reader(f)
    next(publications)  # it skip the first row of the CSV table

    for row in publications:
        pprint(row)  # it prints all the rows except the header
```

It is worth mentioning that, once you have iterated it once, the CSV reader is *consumed* and does not allow you to iterate over the same object twice. For instance, see the following execution where the same reader is iterated twice:

```python
with open("notebook/01-publications.csv", "r", encoding="utf-8") as f:
    publications = reader(f)

    print("-- First iteration")
    for row in publications:
        pprint(row)  # all the rows will be printed, one by one

    print("\n-- Second iteration")
    for row in publications:
        pprint(row)  # no row will be printed
```

### Casting CSV reader into a list

If you want to iterate over the same rows more than one time, one possibility would be to convert your reader into a list object, by using the `list` constructor:

```python
with open("notebook/01-publications.csv", "r", encoding="utf-8") as f:
    publications = reader(f)
    publications_list = list(publications)
```

From now on, even if the file object is closed after executing all the instructions within the `with` block, you can always access (and iterate) the rows defined in the original CSV document since you have stored them within a Python list, as shown in the following excerpt:

```python
print("-- First execution")
for row in publications_list:
    pprint(row)
    
print("\n-- Second execution")
for row in publications_list:
    pprint(row)
```

### CSV table as list of lists

As you can see from the executing the `print` function in the examples above, each row of the CSV table is represented, in Python, as a list of strings. As such, the overall table, after converted it as a list using the related constructor, is defined as a list of list of strings, following the pattern below (using as example the table introduced at the beginning of this tutorial):

```python
my_list = [
    [ "column name", "another name, with a comma" ],              # row 1
    [ "a value", "a value, with a comma" ],                       # row 2
    [ "a quoted \"value\"", "a quoted \"value\", with a comma" ]  # row 3
]
pprint(my_list)
```

As you can see, since strings in Python can be created enclosing their characters between double quotes (i.e. `"`), the only character to escape in the string is the double quote character itself with a slash (i.e. `\"`). Alternatively, you could use the the single quote character (i.e. `'`) for creating strings, avoiding to escape double quote characters, if any:

```python
my_list = [
    [ 'column name', 'another name, with a comma' ],          # row 1
    [ 'a value', 'a value, with a comma' ],                   # row 2
    [ 'a quoted "value"', 'a quoted "value", with a comma' ]  # row 3
]
pprint(my_list)
```

Since a table is a list of list, it can be accessed and modified using the common methods available for the class list, as shown in the following excerpt:

```python
# retrieving the second row in the table
second_row = publications_list[1]  # remember that item indexes starts from 0
print("-- Second row")
pprint(second_row)

# retrieving the third item in the second row
third_item_second_row = second_row[2]
print("\n-- Third item in second row")
pprint(third_item_second_row)

# appending a new row at the end of the list
publications_list.append([
    "10.1080/10273660500441324", 
    "Development of a Species-Specific Model of Cerebral Hemodynamics",
    "2005",
    "1027-3662",
    "journal article",
    "3",
    "6"
])
print("\n-- Updated list")
pprint(publications_list)
```

### CSV writer

Once created or modified a table defined through a list of lists in Python, it can be necessary to store it into a CSV file. To do so, we can use the [constructor `writer`](https://docs.python.org/3/library/csv.html#csv.writer) included in the package `csv`, that must be imported. As we did for loading the content of a CSV file in Python, we use again the `open` function within a `with` statement, but the file path of the first parameter indicates the file where to store the table and we specify `"w"` as the mode to interact with the file to create a new object file, as shown as follows:

```python
from csv import writer

with open("notebook/01-publications-modified.csv", "w", encoding="utf-8") as f:
    publications_modified = writer(f)
    publications_modified.writerows(publications_list)  # it writes all the rows in the list of lists
```

As shown in the code above, the constructor `writer` takes in input again a file object and returns an object having class `_csv.writer`. This class includes some methods to write new rows in the file pointed by the file object. In particular, the [method `writerows`](https://docs.python.org/3/library/csv.html#csv.csvwriter.writerows) can be used to write the table defined as a list of lists (of strings) into the file.

### DictReader and DictWriter

In the previous section, we have seen how to load and store in Python a CSV table defined as a list of lists. There is, though, another approach that can be used to load and store CSV files using Python that represents the CSV tables as list of *dictionaries*. In this case, each key in the dictionary is a label of one of the columns of the table, that must be specified. The [class `DictReader`](https://docs.python.org/3/library/csv.html#csv.DictReader) (that must be imported as usual) is used to load a CSV table in this form, as shown in the following excerpt:

```python
from csv import DictReader

with open("notebook/01-publications-modified.csv", "r", encoding="utf-8") as f:
    publications_modified = DictReader(f)  # it is a reader operating as a list of dictionaries
    publications_modified_dict = list(publications_modified)  # casting the reader as a list

pprint(publications_modified_dict)
```

As you can see from the output of the execution of the code above, the list defined by casting the `DictReader` object, created by passing as input the file object as before, contains dictionaries, where each dictionary represent a row. The values of the cells of each row can be accessed by using the related key which is, as anticipated, one of the label of the columns. It is worth mentioning that, in this case, the first row in the CSV table is always interpreted as the header of the table, and the content of the list of ditionaries will start considering only the values specified from the second row. The following code shows some example about how to interact with such a structure for accessing and modifying the table:

```python
# retrieving the second row in the table
second_row = publications_modified_dict[1]  # remember that item indexes starts from 0
print("-- Second row")
pprint(second_row)

# retrieving the value associated with the column 'title' in the second row
title_value_second_row = second_row["title"]
print("\n-- Value assigned to 'title' in second row")
print(title_value_second_row)

# appending a new row at the end of the list
publications_modified_dict.append({
    "doi": "10.1080/10273660412331292260", 
    "title": "Amplified Molecular Binding of Prion Protein Homologues in Self-Progressive Injury of Neuronal Membranes and Trafficking Systems",
    "publication year": "2003",
    "publication venue": "1027-3662",
    "type": "journal article",
    "issue": "3-4",
    "volume": "5"
})
print("\n-- Updated list of dictionaries")
pprint(publications_modified_dict)
```

As before, once created or modified a table defined through a list of ditionaries, you can store it into a CSV file using the [class `DictWriter`](https://docs.python.org/3/library/csv.html#csv.DictWriter) included in the package `csv` (to be imported, as usual). As we did before, we use again the `open` function within a `with` statement, but the file path of the first parameter indicates the file where to store the table and we specify `"w"` as the mode to interact with the file to create a new object file, as shown as follows:

```python
from csv import DictWriter

with open("notebook/01-publications-modified-dict.csv", "w", encoding="utf-8") as f:
    header = [  # the fields defining the columns must be explicitly specified in the desired order
        "doi", "title", "publication year", "publication venue", "type", "issue", "volume" ]
    
    publications_modified = DictWriter(f, header)
    publications_modified.writeheader()  # the header must be explicitly created in the output file
    publications_modified.writerows(publications_modified_dict)  # it writes all the rows, as usual
```

However, the class `DictWriter` works in a slightly different way of `_csv.writer`. The main differences are:

1. the dictionaries representing the rows do not specify a precise order of the columns to be stored in the CSV file and, as such, it must be explicitly defined;
2. there is no header explicitly specified as a row of the table and, as such, it must be provided to the constructor of the class `DictWriter` and then written as first thing in the file.

For addressing 1), we simply create a new list (the variable `header` of the code above) with all the column labels in the order they must appear in the final file. Instead, for addressing 2), it is sufficient to specify such a new list as the second parameter of the `DictWriter` constructor, after the file object where to store the table; then, it is necessary to write the header of the table calling the [method `writeheader()`](https://docs.python.org/3/library/csv.html#csv.DictWriter.writeheader) before writing the rows with data into the file using the method `writerows`.

### CSV dialects

In the previous sections we showed how to use the classes and functions in the package `csv` in Python to handle CSV documents. It is worth mentioning, though, that CSV has several [dialects](https://docs.python.org/3/library/csv.html#dialects-and-formatting-parameters) that introduce small changes in the structure of a CSV document. For instance, a well-known dialect is named [Tab-separated Values (TSV)](https://en.wikipedia.org/wiki/Tab-separated_values). Here the idea is that one has to use the [tab character](https://en.wikipedia.org/wiki/Tab_key#Tab_characters) to separate the cells of a row instead of the comma. As such, the comma does not have any specific meaning and can be safely used in cell values withou escaping it with quote characters.

For instance, the very first example of CSV table introduced at the beginning of this tutorial can be [represented in TSV](01-example.tsv) as follows:

```
column name	another name, with a comma
a value	a value, with a comma
a quoted "value"	a quoted "value", with a comma
```

Of course, the `csv` package allows one to parse also these additional kinds of formats. Indeed, all the constructors of readers and writers objects (i.e. `reader`, `writer`, `DictReader` and `DictWriter`) can have in input the optional named parameter `dialect` which permits the specification of the dialect to consider for either loading or storing the CSV-like table. For instance, the following code stores the table considered in the previous excerpt of code as a TSV file:

```python
with open("notebook/01-publications-modified-dict.tsv", "w", encoding="utf-8") as f:
    header = [  # the fields defining the columns must be explicitly specified in the desired order
        "doi", "title", "publication year", "publication venue", "type", "issue", "volume" ]
    
    publications_modified = DictWriter(f, header, dialect="excel-tab")  # adding the specific dialect
    publications_modified.writeheader()  # the header must be explicitly created in the output file
    publications_modified.writerows(publications_modified_dict)  # it writes all the rows, as usual
```

In the code above, we have specified a different output file in the `with` statement (i.e.  the extension now is `.tsv`), and we have explicited asked our `DictWriter` to use the tab-separated dialect introduced by Excel (i.e. `dialect="excel-tab"`) to handle the table as a TSV file.

## JavaScript Object Notation (JSON)

Another format well-known in the Web, since it is used in several different scenarios that concern data interchange, is the [Javascript Object Notation (JSON)](https://en.wikipedia.org/wiki/JSON). It is a simple textual format to describe objects which follow the key-value approach to specify data, where the key is always a term written within quotes, while the value can assume any of the following types:

* numbers (integers and floats), specified straight without an markup (e.g. `3` or `3.14`);
* strings, specified between double quotes (e.g. `"a string"`);
* booleans, the values `true` and `false`;
* object, a collection of key-value pairs specified within curly brackets, where each pair is separated with a comma (e.g. `{ "given name": "Silvio", "family name": "Peroni" }`);
* the null value, i.e. `null`, which mimic the `None` value in Python;
* arrays, i.e. lists of values (numbers, strings, booleans, objects, other arrays, etc.) listed between square brackets where each item is separated with a comma (e.g. `[ "a string", "another string", 4, 4.5, true ]`).

Thus, instead of CSV documents in which all the values are actually interpreted as strings, in a JSON document all the values can have different types, as shown above. In addition, each JSON document does not contain necessarily one single object (using curly brackets), but can be defined as an array of objects, and each object can contain (as some of its values) other objects, organising a tree-like structure. An example of such structure is shown in the [exemplar JSON file](01-publications-venues.json) provided in this tutorial, where all the publications and venues specified in the CSV files introduced at the very beginning of the tutorial have been reorganised according to the JSON syntax. As before, to open it as a source file, you can right-click on it in the left panel and select *Open With -> Editor*.

### Loading a JSON document in Python

We need to use specific functions of the [Python package `json`](https://docs.python.org/3/library/json.html) to load a JSON document in Python. In particular, we use the [function `load`](https://docs.python.org/3/library/json.html#json.load) to import in Python a JSON object, that must be imported from the `json` package as usual.

```python
from json import load

with open("notebook/01-publications-venues.json", "r", encoding="utf-8") as f:
    json_doc = load(f)
```

Differntly from the handling of CSV documents, the `load` function (that still takes in input the file object of the file to load) does not return you a reader, but rather it provides directly the representation of the JSON document into the appropriate Python data structures.

### It is a list of dictionaries!

Considering the <a href="01-publications-venues.json">exemplar JSON file</a> we have used in the code above, we can print out on screen the type of the object referred by the `json_doc` variable to see what kind of class it is used to represent such a document, as shown in the following excerpt:

```python
print(type(json_doc))
```

As you can see, a list is used to map the JSON array, which is indeed the most natural choice. In particular, the kind of JSON values mentioned above are converted in Python as follows:

* numbers (e.g. `3` or `3.14`) and strings (e.g. `"a string"`) in JSON are represented with the kinds of values in Python (i.e. `3`, `3.14` and `"a string"`);
* the `true` and `false` boolean values in JSON are represented in Python using `True` and `False` respectively;
* each JSON object is represented by a Python dictionary, having strings specified as keys and the appropriate kind of value assigned to their values;
* JSON arrays, as already mentioned, are represented with Python lists.

Thus you can act upon the JSON object loaded in Python as you do with the classes used to represent the various JSON values. For instance, in the following code, we show some specific item of the JSON array and add another object to the list, which includes a new publication:

```python
# retrieving the second item in the JSON array
second_item = json_doc[1]  # remember that item indexes starts from 0
print("-- Second item")
pprint(second_item)

# retrieving the value associated with the key 'title' in the second item
title_value_second_item = second_item["title"]
print("\n-- Value assigned to 'title' in second item")
print(title_value_second_item)

# appending a new JSON object at the end of the list
json_doc.append({
    "doi": "10.1080/10273660412331292260", 
    "title": "Amplified Molecular Binding of Prion Protein Homologues in Self-Progressive Injury of Neuronal Membranes and Trafficking Systems",
    "publication year": 2003,
    "publication venue": {
        "id": [ "1027-3662" ],
        "name": "Journal of Theoretical Medicine",
        "type": "journal"
    },
    "type": "journal article",
    "issue": "3-4",
    "volume": "5"
})
print("\n-- Updated JSON array (a.k.a. list of dictionaries)")
pprint(json_doc)
```

### Storing a JSON document into a file

We use the [function `dump`](https://docs.python.org/3/library/json.html#json.dump) of the `json` package (to import as usual) to store a dictionary or an array of values into a JSON file, as shown in the following excerpt:

```python
from json import dump

with open("notebook/01-publications-venues-modified.json", "w", encoding="utf-8") as f:
    dump(json_doc, f, ensure_ascii=False, indent=4)
```

The `dump` function takes in input two mandatory positional parameters - i.e. the Python representation of a JSON document as the first parameter and the file object referring to the file where to store the JSON document. In addition, it can takes several other optional named parameters, two of which are strongly suggested and have been used in the code above. 

The parameter `ensure_ascii` (assigned to `True` by defalut) is responsible to keep every string value compliant with the [ASCII character encoding](https://en.wikipedia.org/wiki/ASCII), which will result in escaping all non-ASCII characters (that are only 128 characters). This is very undesirable when we have natural language text in the JSON object we want to store since, for instance, all the characters with accents (e.g. `"è"`) will be encoded in a different way (in the example, `"\u00e8"`, that is the UTF-8 code of the character `"è"`). That is why the code above sets the `ensure_ascii` input parameter to `False`: to avoid such an escaping, preserving the original characters as they are (i.e. encoded in UTF-8).

Instead, the parameter `indent` is used to specify how many white spaces to add for indenting the various key-value pairs in the JSON document. The choice to specify the indent is only for human consumption, since a machine does not care about how these pairs are visually organised in the document. Indeed, the JSON document

```
{ "given name": "Silvio", "family name": "Peroni }
```

and the JSON document

```
{ 
    "given name": "Silvio", 
    "family name": "Peroni" 
}
```

are actually storing the same data, but the second is usually easier to read for humans. That is why the code above sets the input parameter `indent` to `4`, meaning that four spaces must be used to indent the various JSON pairs.
