# Interacting with databases using Pandas

> 来源：[博洛尼亚大学 Digital Humanities and Digital Knowledge 课程团队](https://thinkcompute.github.io/21-querying-databases.html)  
> 许可：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)  
> 语言：英文补充资料  
> 版本：0c6a477bcdb50fd73b3b06d08a8f56324c86454f  
> 署名：改编自 Silvio Peroni、Ivan Heibi、Arcangelo Massari（2025）《Think and Compute: a Primer for Digital Humanists》，原作采用 CC BY 4.0。

# Interacting with databases using Pandas

In this chapter, we show how to use Pandas data frames to interact with SQL-based and graph-based databases.

## Data available in different sources

Often, when you have to deal with and reuse existing data, the answer to a query can be possible only by combining data available in different databases. In addition, such databases can expose their data using different technologies (e.g. an SQLite database and an RDF triplestore). Thus, it is important to have a smooth method that allows one to take data from different sources, to expose these data according to a similar interface, and finally to make some additional operation on these data that, in principle, can be seen as coming from a unique abstract source.

Pandas, thanks to its standard library and additional plugins developed for it, enables us to use it as a proxy model for getting and comparing data coming from different sources (and even different formats). A few tutorials ago, indeed, we have seen how to read data stored as CSV documents using Pandas. We can use similar functions to read a result of a query sent to a database as it is a source of information. In this tutorial, we see how to do it with SQLite and Blazegraph, i.e. the two databases used in the previous tutorials.

## Reading data from SQLite

Pandas makes available the [method `read_sql`](https://pandas.pydata.org/docs/reference/api/pandas.read_sql.html) which enables us, among the other things, to query an SQL-based database using an SQL query and to expose the answer returned as a classic Pandas data frame. This function takes in input two mandatory parameters that are the SQL query to execute on the database and the connection to it, and returns a data frame built on the data and the parameter specified in the SQL query. For instance, the following code takes the title of all the journal articles included in the table `JournalArticle`:

```python
from sqlite3 import connect
from pandas import read_sql

with connect("notebook/05-publications.db") as con:
    query = "SELECT title FROM JournalArticle"
    df_sql = read_sql(query, con)
    
df_sql  # show the content of the result of the query
```

It is worth mentioning that, to enable the correct definition of the results of the query into a data frame, it is always better first to create all the necessary data frames within the `with` clause, and then start to work on them "offline", once the connection to the database has been closed. Otherwise, you could observe some unexpected behaviours.

Finally, it is worth mentioning that the data type used in the database are converted into the appropriate data type in Pandas. Thus, if a column has been defined as containing integers in the database, we get back the same data type for the column in the data frame. This is clear when we try to retrieve, for instance, an entire table from the SQLite database:

```python
with connect("notebook/05-publications.db") as con:
    query = "SELECT * FROM JournalArticle"
    df_journal_article_sql = read_sql(query, con)

# Show the series of the column 'publicationYear', which as 'dtype'
# specifies 'int64', as expected
df_journal_article_sql["publicationYear"]
```

## Reading data from Blazegraph

Even if Pandas does not make available any reading method to interact with RDF triplestores, some developers has implemented a facility that permits us to interact directly with a SPARQL endpoint provided by an RDF triplestore such as Blazegraph, i.e. the [library `sparql_dataframe`](https://github.com/lawlesst/sparql-dataframe). This library is a wrapper for a SPARQL query and shows the answer to such a query as a Pandas data frame. We can install the library using the usual command:

```
pip install sparql_dataframe
```

The function `get` is called to perform such an operation, and it takes in input three parameters: the URL of the SPARQL endpoint to contact, the query to execute, and a boolean specifying if to contact the SPARQL endpoint using the [POST HTTP method](https://en.wikipedia.org/wiki/POST_(HTTP)) (strongly suggested, otherwise it could not work correctly). An example of execution of such a function is shown in the following excerpt:

```python
from sparql_dataframe import get

endpoint = "http://127.0.0.1:9999/blazegraph/sparql"
query = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?journal_article ?title
WHERE {
    ?journal_article rdf:type schema:ScholarlyArticle .
    ?journal_article schema:name ?title .
}
"""
df_sparql = get(endpoint, query, True)
df_sparql
```

Due to the implementation of the `get` function in the `sparql_dataframe` package, though, the values returned by running the SPARQL query will be inferred automatically by looking at all the values of a certain column. Thus, if one wants to change the data type of the values associated to a particular column, one has to cast the column on purpose and the reassigning the column to the data frame. For instance, let us build a query that takes information of all the publications available in the triplestore:

```python
publication_query = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?internalId ?doi ?publicationYear ?title ?issue ?volume ?publicationVenue
WHERE {
    VALUES ?type {
        schema:ScholarlyArticle
        schema:Chapter
    }
    
    ?internalId rdf:type ?type .
    ?internalId schema:identifier ?doi .
    ?internalId schema:datePublished ?publicationYear .
    ?internalId schema:name ?title .
    ?internalId schema:isPartOf ?publicationVenue .
        
    OPTIONAL {
        ?internalId schema:issueNumber ?issue .
        ?internalId schema:volumeNumber ?volume .
    }
}
"""

df_publications_sparql = get(endpoint, publication_query, True)
df_publications_sparql
```

It is worth mentioning that the optional group in the SPARQL query (`OPTIONAL { ... }`) is used to allow information to be added to the solution if it is available, otherwise the related variables will be left empty.

## Fixing some issues

As you can observed from the result of the previous query, the data frame created contains some basic information depicted by the variable names chosen, that are specified in the query itself for being equal to those returned in the last SQL query done above. 

However, one unexpected behaviour is the way the columns `issue` and `volume` is handled. To see this, we use the [attribute `dtypes`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dtypes.html) of our data frame to see how things are handled:

```python
df_publications_sparql.dtypes
```

As you can see, the two columns mentioned above have been assigned with a float data type, which has been inferred by Pandas by looking at the values of these two columns. In order to change it into an appropriate kind of value, e.g. a string, we have to overwrite the data type of the entire data frame (using the [method `astype`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.astype.html) that takes in input the new data type) and/or the data type of specific columns. For doing the last operation, we have to reassign the columns with the new types to the data frame using the following syntax:

```
<data frame>[<column name>] = <data frame>[<column name>].astype(<new data type>)
```

For instance, to reassign the columns `issue` and `volume` to the type `"string"`, we can run the following commands:

```python
df_publications_sparql["issue"] = df_publications_sparql["issue"].astype("string")
df_publications_sparql["volume"] = df_publications_sparql["volume"].astype("string")

df_publications_sparql.dtypes
```

Similarly, if you want to replace the `NaN` values associated to the same two columns when no value is available, you can use the data frame [method `fillna`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.fillna.html), which enables one to replace all `NaN` in the data frame with a value of your choice passed as input:

```python
df_publications_sparql = df_publications_sparql.fillna("")

df_publications_sparql
```

Of course, this allowed us to remove all `NaN` values. However, if you look at the table and in particular to the columns `issue` and `volume`, you can see something that is still a bit in these two columns. 

Indeed, the two strings defining issues and volumes associated with an article are, actually, the mere cast of the floating value into a string and, as such, they contain the `.0` part of the float that we need to remove. Since the same pattern is repeated in all the values of these two columns, we could apply a similar operation to all their values to clean them up. For doing that, we use the [method `apply`](https://pandas.pydata.org/docs/reference/api/pandas.Series.apply.html) of the class `Series`, which allows us to apply an input function to all the values of a column and to store, in each value, what such a function returns.

A function that would allow us perform such an operation is the following one:

```python
def remove_dotzero(s):
    return s.replace(".0", "")
```

The function above takes in input a string (i.e. the value of a cell) and remove the string `".0"` from there, if present. Thus, passing this function to the method `apply` of each column and then to assign the modified column back to the data frame will fix the issue, as shown as follows:

```python
df_publications_sparql["issue"] = df_publications_sparql["issue"].apply(remove_dotzero)
df_publications_sparql["volume"] = df_publications_sparql["volume"].apply(remove_dotzero)

df_publications_sparql
```

## Combining data

In the previous section, we have introced how to obtain data from existing databases and how to manipulate them using Pandas. However, in real case scenarios, an answer to a certain query can arrive only from mixing partial data from two distinct databases. Thus, it is important to implement some mechanisms to mash data up together, clean them if needed (e.g. removing duplicates), and to return them in a certain order (e.g. alphabetically). Of course, Pandas can be used to perform all these operations.

Suppose that we want to find, by querying all the databases, all the titles and year of publication of all publications they contain (independently from their type), ordered from the oldest one to the newest one. To simplify the job for this tutorial, we could consider the two data frames computed before, i.e. `df_journal_article_sql` and `df_publications_sparql`, as the two coming from two different databases.

First of all, we need something that allows us to concat two or more data frames together. However, in order to do that, it is important that, first of all, all the data frames to contact share the same columns. Thus, if necessary, it is important to rename the columns as we have seen in a previous tutorial. In this case, instead, we have already created the data frames with the same column names and, as such, we can proceed with the concat operation, i.e. obtaining a new data frame by concatenating the rows contained in both the data frames.

This operation is implemented by the [function `concat`](https://pandas.pydata.org/docs/reference/api/pandas.concat.html), that takes in input a list of data frames and return a new data frame with all the rows concatenated. In addition, it can also take in input the named parameter `ignore_index` that, if set to `True`, will reindex all the rows from the beginning in the new data frame, as shown in the following code:

```python
from pandas import concat

df_union = concat([df_journal_article_sql, df_publications_sparql], ignore_index=True)
df_union
```

After having obtained a new data frame concatenating the other two, we need to filter out duplicates. Once can follow different approaches for doing so. In this context, we will use the DOIs of the publications to perform the filtering. 

A [DOI (Digital Object Identifier)](https://en.wikipedia.org/wiki/Digital_object_identifier) is a persistent identifier used to identify publications uniquely worldwide. Thus, if a publication is included in two distinct databases, it should have the same DOI despite the local identifiers the databases may use.

Once this aspect is clear, we can perform a removal of rows using the [method `drop_duplicates`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop_duplicates.html) of the class `DataFrame`. This method allows one to specify the optional named parameter `subset` with the list of columns names to use to identify similar rows. If such a named parameter is not specified, only identical rows (those having all the values in full match) are removed from data frame. Thus, we can perform the removal of duplicates as follows:

```python
df_union_no_duplicates = df_union.drop_duplicates(subset=["doi"])
df_union_no_duplicates
```

Then, we have finally to sort rows in ascending order considering the publication year, and then to return just the columns publication year and title and year of publication of each row. In Pandas, the sorting can be performed using the [method `sort_values`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html) of the class `DataFrame`, that takes in input the name of the column to use to perform the sorting, as shown as follows:

```python
df_union_no_duplicates_sorted = df_union_no_duplicates.sort_values("publicationYear")
df_union_no_duplicates_sorted
```

Finally, to select a sub-data frame, we use the approach adopted in past tutorial, by creating a new data frame selecting only some of the columns of another one:

```python
df_final = df_union_no_duplicates_sorted[["title", "publicationYear"]]
df_final
```
