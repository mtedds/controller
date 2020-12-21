create table state (
	Name text,
	Value
);

create table gateway (
	GatewayId integer primary key,
	GatewayName text,
	BrokerHost text,
	ClientId text,
	SubscribeTopic text,
	PublishTopic text,
	Username text,
	Password text,
	LastSeen text
);

create table node (
        NodeId integer primary key,
	GatewayId integer,
        MySensorsNodeId integer,
        NodeName text,
	NodeType integer,
        LibraryVersion text,
        CodeVersion text,
        LastSeen text
);

create table sensor (
        SensorId integer primary key,
	NodeId integer,
        MySensorsSensorId integer,
        SensorName text,
        SensorType text,
        VariableType text,
        CurrentValue text,
        LastSeen text
);

create view v_sensor as
select SensorId
       , NodeId
       , MySensorsSensorId
       , SensorName
       , SensorType
       , VariableType
       , CurrentValue
       , datetime(lastseen, 'unixepoch') as LastSeen
from sensor;

create table timedtrigger (
        TimedTriggerId integer primary key,
	Time text,
        ActionId integer
);

create table action (
        ActionId integer primary key,
	SensorName text,
        VariableType text,
        SetValue text
);

