import pytest
from graphql.type import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLString,
)

from ..dynamic import Dynamic
from ..enum import Enum
from ..field import Field
from ..inputfield import InputField
from ..inputobjecttype import InputObjectType
from ..interface import Interface
from ..objecttype import ObjectType
from ..scalars import Int, String
from ..structures import List, NonNull
from ..schema import GrapheneGraphQLSchema, resolve_type


def create_type_map(types, auto_camelcase=True):
    query = GraphQLObjectType("Query", {})
    schema = GrapheneGraphQLSchema(query, types=types, auto_camelcase=auto_camelcase)
    return schema.type_map


def test_enum():
    class MyEnum(Enum):
        """Description"""

        foo = 1
        bar = 2

        @property
        def description(self):
            return "Description {}={}".format(self.name, self.value)

        @property
        def deprecation_reason(self):
            if self == MyEnum.foo:
                return "Is deprecated"

    type_map = create_type_map([MyEnum])
    assert "MyEnum" in type_map
    graphql_enum = type_map["MyEnum"]
    assert isinstance(graphql_enum, GraphQLEnumType)
    assert graphql_enum.name == "MyEnum"
    assert graphql_enum.description == "Description"
    assert graphql_enum.values == {
        'foo': GraphQLEnumValue(
            value=1, description="Description foo=1", deprecation_reason="Is deprecated"
        ),
        'bar': GraphQLEnumValue(value=2, description="Description bar=2"),
    }


def test_objecttype():
    class MyObjectType(ObjectType):
        """Description"""

        foo = String(
            bar=String(description="Argument description", default_value="x"),
            description="Field description",
        )
        bar = String(name="gizmo")

        def resolve_foo(self, bar):
            return bar

    type_map = create_type_map([MyObjectType])
    assert "MyObjectType" in type_map
    graphql_type = type_map["MyObjectType"]
    assert isinstance(graphql_type, GraphQLObjectType)
    assert graphql_type.name == "MyObjectType"
    assert graphql_type.description == "Description"

    fields = graphql_type.fields
    assert list(fields.keys()) == ["foo", "gizmo"]
    foo_field = fields["foo"]
    assert isinstance(foo_field, GraphQLField)
    assert foo_field.description == "Field description"

    assert foo_field.args == {
        "bar": GraphQLArgument(
            GraphQLString,
            description="Argument description",
            default_value="x",
            out_name="bar",
        )
    }


def test_dynamic_objecttype():
    class MyObjectType(ObjectType):
        """Description"""

        bar = Dynamic(lambda: Field(String))
        own = Field(lambda: MyObjectType)

    type_map = create_type_map([MyObjectType])
    assert "MyObjectType" in type_map
    assert list(MyObjectType._meta.fields.keys()) == ["bar", "own"]
    graphql_type = type_map["MyObjectType"]

    fields = graphql_type.fields
    assert list(fields.keys()) == ["bar", "own"]
    assert fields["bar"].type == GraphQLString
    assert fields["own"].type == graphql_type


def test_interface():
    class MyInterface(Interface):
        """Description"""

        foo = String(
            bar=String(description="Argument description", default_value="x"),
            description="Field description",
        )
        bar = String(name="gizmo", first_arg=String(), other_arg=String(name="oth_arg"))
        own = Field(lambda: MyInterface)

        def resolve_foo(self, args, info):
            return args.get("bar")

    type_map = create_type_map([MyInterface])
    assert "MyInterface" in type_map
    graphql_type = type_map["MyInterface"]
    assert isinstance(graphql_type, GraphQLInterfaceType)
    assert graphql_type.name == "MyInterface"
    assert graphql_type.description == "Description"

    fields = graphql_type.fields
    assert list(fields.keys()) == ["foo", "gizmo", "own"]
    assert fields["own"].type == graphql_type
    assert list(fields["gizmo"].args.keys()) == ["firstArg", "oth_arg"]
    foo_field = fields["foo"]
    assert isinstance(foo_field, GraphQLField)
    assert foo_field.description == "Field description"
    assert not foo_field.resolve  # Resolver not attached in interfaces
    assert foo_field.args == {
        "bar": GraphQLArgument(
            GraphQLString,
            description="Argument description",
            default_value="x",
            out_name="bar",
        )
    }


def test_inputobject():
    class OtherObjectType(InputObjectType):
        thingy = NonNull(Int)

    class MyInnerObjectType(InputObjectType):
        some_field = String()
        some_other_field = List(OtherObjectType)

    class MyInputObjectType(InputObjectType):
        """Description"""

        foo_bar = String(description="Field description")
        bar = String(name="gizmo")
        baz = NonNull(MyInnerObjectType)
        own = InputField(lambda: MyInputObjectType)

        def resolve_foo_bar(self, args, info):
            return args.get("bar")

    type_map = create_type_map([MyInputObjectType])
    assert "MyInputObjectType" in type_map
    graphql_type = type_map["MyInputObjectType"]
    assert isinstance(graphql_type, GraphQLInputObjectType)
    assert graphql_type.name == "MyInputObjectType"
    assert graphql_type.description == "Description"

    other_graphql_type = type_map["OtherObjectType"]
    inner_graphql_type = type_map["MyInnerObjectType"]
    container = graphql_type.out_type(
        {
            "bar": "oh!",
            "baz": inner_graphql_type.out_type(
                {
                    "some_other_field": [
                        other_graphql_type.out_type({"thingy": 1}),
                        other_graphql_type.out_type({"thingy": 2}),
                    ]
                }
            ),
        }
    )
    assert isinstance(container, MyInputObjectType)
    assert "bar" in container
    assert container.bar == "oh!"
    assert "foo_bar" not in container
    assert container.foo_bar is None
    assert container.baz.some_field is None
    assert container.baz.some_other_field[0].thingy == 1
    assert container.baz.some_other_field[1].thingy == 2

    fields = graphql_type.fields
    assert list(fields.keys()) == ["fooBar", "gizmo", "baz", "own"]
    own_field = fields["own"]
    assert own_field.type == graphql_type
    foo_field = fields["fooBar"]
    assert isinstance(foo_field, GraphQLInputField)
    assert foo_field.description == "Field description"


def test_objecttype_camelcase():
    class MyObjectType(ObjectType):
        """Description"""

        foo_bar = String(bar_foo=String())

    type_map = create_type_map([MyObjectType])
    assert "MyObjectType" in type_map
    graphql_type = type_map["MyObjectType"]
    assert isinstance(graphql_type, GraphQLObjectType)
    assert graphql_type.name == "MyObjectType"
    assert graphql_type.description == "Description"

    fields = graphql_type.fields
    assert list(fields.keys()) == ["fooBar"]
    foo_field = fields["fooBar"]
    assert isinstance(foo_field, GraphQLField)
    assert foo_field.args == {
        "barFoo": GraphQLArgument(
            GraphQLString,
            default_value=None,
            out_name="bar_foo"
        )
    }


def test_objecttype_camelcase_disabled():
    class MyObjectType(ObjectType):
        """Description"""

        foo_bar = String(bar_foo=String())

    type_map = create_type_map([MyObjectType], auto_camelcase=False)
    assert "MyObjectType" in type_map
    graphql_type = type_map["MyObjectType"]
    assert isinstance(graphql_type, GraphQLObjectType)
    assert graphql_type.name == "MyObjectType"
    assert graphql_type.description == "Description"

    fields = graphql_type.fields
    assert list(fields.keys()) == ["foo_bar"]
    foo_field = fields["foo_bar"]
    assert isinstance(foo_field, GraphQLField)
    assert foo_field.args == {
        "bar_foo": GraphQLArgument(
            GraphQLString,
            default_value=None,
            out_name="bar_foo"
        )
    }


def test_objecttype_with_possible_types():
    class MyObjectType(ObjectType):
        """Description"""

        class Meta:
            possible_types = (dict,)

        foo_bar = String()

    type_map = create_type_map([MyObjectType])
    graphql_type = type_map["MyObjectType"]
    assert graphql_type.is_type_of
    assert graphql_type.is_type_of({}, None) is True
    assert graphql_type.is_type_of(MyObjectType(), None) is False


def test_resolve_type_with_missing_type():
    class MyObjectType(ObjectType):
        foo_bar = String()

    class MyOtherObjectType(ObjectType):
        fizz_buzz = String()

    def resolve_type_func(root, info):
        return MyOtherObjectType

    type_map = create_type_map([MyObjectType])
    with pytest.raises(AssertionError) as excinfo:
        resolve_type(resolve_type_func, type_map, "MyOtherObjectType", {}, {}, None)

    assert "MyOtherObjectTyp" in str(excinfo.value)
