###
# SQL Alchemy helper functions
###
from sqlalchemy import create_engine
from sqlalchemy.event import listen
from sqlalchemy.orm import sessionmaker, class_mapper, ColumnProperty
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator, VARCHAR
import json

### Engine Classes

class Engine(object):
    """An object that can be used to connect to a database with SQLAlchemy.
    
    Will usually be used through a descendant specific to the flavor of SQL the database uses. Used to create connection sessions to the database:
        
    .. code-block:: python
    
        session = engine.Session()
    
    Arguments:
        url (str): URL for the database.
        echo (bool, optional): Can be used to set the engine to echo all of the SQL statements sent and received to the console. Defaults to False.
    
    Attributes:
        engine: The underlying SQLAlchemy engine object.
        Session: A class that can instantiate connection sessions to this database.
        
    """

    def __init__(self, url, echo=False, **engine_kwargs):
        self._url = url
        self.engine = create_engine(self._url, echo=echo, **engine_kwargs)
        self.Session = sessionmaker(bind=self.engine)
    
    def initialize_tables(self, declarative_metadata, re_initialize=False):
        if re_initialize is True:
            declarative_metadata.drop_all(self.engine)
        declarative_metadata.create_all(self.engine)

class SQLiteEngine(Engine):
    """An object that can be used to connect to an SQLite database with SQLAlchemy.
    
    Arguments:
        path (str): The filepath for the database. An empty string will make an engine that interacts with an in-memory database.
        echo (bool, optional): If True, the engine will echo all of the SQL statements sent and received to the console. Defaults to False.
        foreign_keys (bool, optional): If True, the engine will automatically enable foreign key support in all connections it creates to the database using :func:`sqlite_foreign_keys`. Defaults to False.
    
    Attributes:
        engine: The underlying SQLAlchemy engine object.
        Session: A class that can instantiate connection sessions to this database.
        
    """

    def __init__(self, path, echo=False, foreign_keys=False, **engine_kwargs):
        '''if path == "":
            #if in-memory table, set some extra engine arguments to keep everything in a single connection object, since the database only exists within the scope of that connection.
            engine_kwargs.update(dict(
                connect_args={"check_same_thread":False},
                poolclass=StaticPool,
            ))'''
        
        super(SQLiteEngine, self).__init__(
            'sqlite:///{db}'.format(db=path),
            echo,
            #**engine_kwargs,
        )
        
        if foreign_keys:
            #Automatically enable foreign key support each time connects database, required for database side deletion cascades in sqlite.
            listen(self.engine, "connect", sqlite_foreign_keys)

class SQLiteAuthenticatedEngine(SQLiteEngine):
    #Placeholder to remind that authentication should subclass SQLiteEngine
    pass

class PostgressEngine(Engine):
    """An object that can be used to connect to a Postgres database with SQLAlchemy.
    
    Arguments:
        host (str): The hostname or ip address for the database.
        name (str): The name of the database on the host machine.
        username (str): The username being used to log into the database.
        password (str): The password corresponding to the username.
        echo (bool, optional): Can be used to set the engine to echo all of the SQL statements sent and received to the console. Defaults to False.
    
    Attributes:
        engine: The underlying SQLAlchemy engine object.
        Session: A class that can instantiate connection sessions to this database.
        
    """

    def __init__(self, host, name, username, password, echo=False, **engine_kwargs):
        super(PostgressEngine, self).__init__(
            url = 'postgresql://{username}:{password}@{host}/{name}'.format(
                username = username,
                password = password,
                host = host,
                name = name
            ),
            echo = echo,
            #**engine_kwargs,
        )

### Custom Column Types

class JSONType(TypeDecorator):
    #From SQLAlchemy documentation: docs.sqlalchemy.org/en/rel_0_9/core/custom_types.html#marshal-json-strings
    impl = VARCHAR
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
            
        return value
    
    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        
        return value

### Class Mixins

class DynamicReprMixin(object):
    # provides a dynamic stringification function that finds all column properties for the class, creating a string of the form:
    # <Class(column1=value1, column2=value2, ...)>
    
    def _dict_and_order(self):
        key_order = [prop.key for prop in class_mapper(self.__class__).iterate_properties if isinstance(prop, ColumnProperty)]
        column_dict = dict([(key, self.__dict__.get(key,"undefined")) for key in key_order])
        return column_dict, key_order
    
    def dict(self):
        column_dict, key_order = self._dict_and_order()
        return column_dict
    
    def __repr__(self):
        prop_dict = self.dict()
        return "<{class_name}({columns_str})>".format(
            class_name = self.__class__.__name__,
            columns_str = ", ".join(["{key}={value}".format(key=key, value=repr(value)) for key, value in prop_dict.items()]),
        )

###
# Unique Objects recipe from 
# https://bitbucket.org/zzzeek/sqlalchemy/wiki/UsageRecipes/UniqueObject
###
def _unique(session, cls, hashfunc, queryfunc, constructor, *args, **kwargs):
    cache = getattr(session, '_unique_cache', None)
    if cache is None:
        session._unique_cache = cache = {}

    key = (cls, hashfunc(*args, **kwargs))
    if key in cache:
        return cache[key]
    else:
        with session.no_autoflush:
            q = session.query(cls)
            q = queryfunc(q, *args, **kwargs)
            obj = q.first()
            if not obj:
                obj = constructor(*args, **kwargs)
                session.add(obj)
        cache[key] = obj
        return obj

class UniqueMixin(object):
    @classmethod
    def unique_hash(cls, *args, **kwargs):
        raise NotImplementedError()

    @classmethod
    def unique_filter(cls, query, *args, **kwargs):
        raise NotImplementedError()

    @classmethod
    def as_unique(cls, session, *args, **kwargs):
        return _unique(
            session,
            cls,
            cls.unique_hash,
            cls.unique_filter,
            cls,
            *args, **kwargs
        )
               
# End Unique Objects recipe

class PromptMergeMixin(object):
    
    @classmethod
    def prompt_merge(cls, instance, session):
        
        unique_query = session.query(cls)
        for unique_key in cls._unique_keys:
            unique_query = unique_query.filter(getattr(cls, unique_key) == getattr(instance, unique_key))
        existing = unique_query.one_or_none()
        if existing:
            existing_dict = existing.dict()
            existing_dict.pop("id", None)
            new_dict = instance.dict()
            new_dict.pop("id", None)
            if new_dict == existing_dict:
                pass
            else:
                print("Existing:")
                print(existing_dict)
                print("New:")
                print(new_dict)
                while True:
                    choice = input("Please pick (E)xisting or (n)ew to save: ")
                    if not choice or choice.lower() == "e":
                        return existing
                    elif choice.lower() == "n":
                        instance.id = existing.id
                        instance = session.merge(instance)
                        return instance
            
        else:
            session.add(instance)
            return instance

### Events

def sqlite_foreign_keys(dbapi_connection, connection_record):
    """ Turns on foreign key support for the duration of a connection to a SQLite database.
    
        SQLite does not track foreign keys by default. You must turn on foreign keys each time you connect to a SQLite database. Attach this to a listener to run it automatically each time you connect:
        
        .. code-block:: python
        
            sqlalchemy.event.listen(ScoresCacheDB.engine, "connection", hermes.sqlite_foreign_keys)
            
        (This happens automatically when a :class:`SQLiteEngine` object is created with foreign_keys=True.)
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()