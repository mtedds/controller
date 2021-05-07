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

create view v_gateway as
select
	GatewayId,
	GatewayName,
	BrokerHost,
	ClientId,
	SubscribeTopic,
	PublishTopic,
	Username,
	Password,
	datetime(lastseen, 'unixepoch') as LastSeen
from gateway
;

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

create view v_node as
select NodeId
       , GatewayId
       , MySensorsNodeId
       , NodeName
       , NodeType
       , LibraryVersion
       , CodeVersion
       , datetime(lastseen, 'unixepoch') as LastSeen
from node;

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
        Description text,
        Day integer
	    Time text,
        ActionId integer,
        LastSeen text
);

create view v_timedtrigger as
select timedtriggerid
       , description
       , day
       , time
       , actionid
       , status
       , datetime(lastseen, 'unixepoch') as LastSeen
from timedtrigger;


create table action (
        ActionId integer primary key,
	    SensorName text,
	    TimedTriggerToUpdate integer,
        VariableType text,
        SetValue text,
        LastSeen text
);

create view v_action as
select actionid, sensorname, timedtriggertoupdate, variabletype, setvalue, datetime(lastseen, 'unixepoch') as LastSeen
from action;