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
	"ESPP-MQTT",
	"localhost:1883",
	"mycontroller-client-mqtt",
	"mygateway1-out",
	"mygateway1-in",
	"",
	"",
	""
);

