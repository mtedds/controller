drop table state;
create table state (
	Name text,
	Value
);

drop table gateway;
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

drop table node;
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

drop table sensor;
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

drop table timedtrigger;
create table timedtrigger (
        TimedTriggerId integer primary key,
	Time text,
        ActionId integer
);

drop table action;
create table action (
        ActionId integer primary key,
	SensorName text,
        VariableType text,
        SetValue text
);

