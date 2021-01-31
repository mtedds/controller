delete from Gateway;
insert into Gateway (
	GatewayId,
	GatewayName,
	BrokerHost,
	ClientId,
	SubscribeTopic,
	PublishTopic,
	Username,
	Password,
	LastSeen
)
values (
	1,
	"ISG",
	"localhost:1883",
	"ISGclient",
	"ISG",
	"ISG-in",
	"",
	"",
	""
);

insert into Gateway (
	GatewayId,
	GatewayName,
	BrokerHost,
	ClientId,
	SubscribeTopic,
	PublishTopic,
	Username,
	Password,
	LastSeen
)
values (
	2,
	"ENSUITE",
	"localhost:1883",
	"mycontroller-client-mqtt",
	"ensuite-out",
	"ensuite-in",
	"",
	"",
	""
);

insert into Gateway (
	GatewayId,
	GatewayName,
	BrokerHost,
	ClientId,
	SubscribeTopic,
	PublishTopic,
	Username,
	Password,
	LastSeen
)
values (
	3,
	"ESPP-MQTT2",
	"localhost:1883",
	"mycontroller-client-mqtt2",
	"mygateway2-out",
	"mygateway2-in",
	"",
	"",
	""
);

insert into Gateway (
	GatewayId,
	GatewayName,
	BrokerHost,
	ClientId,
	SubscribeTopic,
	PublishTopic,
	Username,
	Password,
	LastSeen
)
values (
	4,
	"EMPTY",
	"localhost:1883",
	"empty",
	"empty-out",
	"empty-in",
	"",
	"",
	""
);

