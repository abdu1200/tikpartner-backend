import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()

"""
- the WebSocket URL is used when a user makes a WebSocket connection request, and it triggers the connect method. This URL typically includes parameters like conversation_id, which is used to identify the specific room or conversation.

- The connect method establishes the WebSocket connection, adds it to the room group, and accepts it for interaction.
- The disconnect method removes the WebSocket connection from the room group, effectively stopping interaction for that user.

"""

class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        #- The scope contains WebSocket-related information (such as user info, websocket url info..)
        self.user = self.scope["user"]    #- self.scope["user"] refers to the current user making the WebSocket request. It's similar to how the user is retrieved in Django views but in the context of WebSocket connections.
        
        # here it checks if the user is authenticated using django's authentication system
        if not self.user.is_authenticated:
            await self.close()    #self.close() terminates the WebSocket connection or establishment, closing it for the current user.
            return
            
        #The conversation ID is extracted from the WebSocket URL, w/h the URL is used when a user makes a WebSocket connection request, and it triggers the connect method. This URL typically includes parameters like conversation_id, which is used to identify the specific room or conversation.     
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # This checks if the user is a participant in the conversation. It calls the user_in_conversation method (which checks the database for the user's participation in the conversation).
        if not await self.user_in_conversation(self.user.id, self.conversation_id):
            await self.close()
            return
            
        #2 This adds the user's established WebSocket connection to the room group(websocket group), but the user can't interact until 'await self.accept()' is called, until the connection is accepted, the user can't send or receive messages.
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name  #1 at this point the websocket connection for a specific user/client is established and assigned a 'self.channel_name' 
        )
        
        await self.accept()    #This line formally accepts the WebSocket connection, allowing communication between the client(websocket client) and the server(websocket server).
        

        # After accepting the connection, the method retrieves the conversation's message history (using get_conversation_messages), then sends this history back to the client via the WebSocket. This is useful for loading previous messages when the user first connects to the chat.
        messages = await self.get_conversation_messages(self.conversation_id)
        await self.send(text_data=json.dumps({
            'type': 'history',
            'messages': messages
        }))


    async def disconnect(self, close_code):
        # Leave room group  # The disconnect method removes the WebSocket connection from the room group, effectively stopping interaction for that user.
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )


    # The receive method handles incoming WebSocket messages from the user
    async def receive(self, text_data):     #text_data is a json w/h is an incoming WebSocket message as a string
        data = json.loads(text_data)  #Converts the received JSON-formatted string (text_data) into a Python dictionary (data)
        #text_data typically look like '{"type": "message", "message": "Hello, how are you?", "attachments": []}' or '{"type": "read"}'

        message_type = data.get('type', 'message')  #Retrieves the "type" field/key from the dictionary, and if its missing, it defaults it to 'message'
        
        if message_type == 'message':      #If message_type is "message", it means the user is sending a chat message.
            message = data['message']
            attachments = data.get('attachments', [])   #This retrieves any attachments (defaulting to an empty list if none exist).
            
            #saving the message to the database using self.save_message()
            message_obj = await self.save_message(
                conversation_id=self.conversation_id,
                sender_id=self.user.id,
                content=message,
                attachments=attachments
            )
            
            #sending the message to all users in the chat room or room group or websocket group using group_send()
            await self.channel_layer.group_send(   #'self.channel_layer.group_send' sends the message to all users in the group using their assigned self.channel_name (which represents their WebSocket connection).
                self.room_group_name,
                {                                   #this is a dictionary, but just like the incoming websocket message, when this message get sent over the websocket, it gets converted to a JSON-encoded string(using await 'self.send' )
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id,
                    'sender_name': self.user.username,
                    'message_id': message_obj['id'],
                    'attachments': attachments,
                    'created_at': message_obj['created_at']
                }
            )
        elif message_type == 'read':      # if the type of message(message_type) that is sent from the user/client is "read", w/h is like this: '{"type": "read"}'
            # Mark messages as read 
            await self.mark_messages_as_read(self.conversation_id, self.user.id)
            
            # Notify others that messages have been read
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'messages_read',
                    'reader_id': self.user.id   # This is notifying all the users in the conversation that the current user (self.user.id) has read the messages. The message type 'messages_read' is sent to the room group, and all connected users are informed of this update.
                }
            )
# Each WebSocket client (user) represents its own frontend, where the user can send and receive messages in real time. When a user establishes a WebSocket connection, it's like their personal communication channel to interact with the backend and receive updates.




#messages sent using 'self.channel_layer.group_send' are sent directly to the WebSocket clients (users or channel_names) connected to the room group. 
#The websocket server sends the message to all users in the specified group (self.room_group_name). 
#The WebSocket clients(users) then receive the message and handle it according to the specified message type(chat_message or messages_read or ...)

#the real time things, like seeing the message pop up when ur in the conversation or seeing the double tick when somebody sees ur message



    # Receiving the pushed dictionary message from room group and formatting it to json and sending it to the websocket clients(using their channels_name or websocket connection)
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'message_id': event['message_id'],
            'attachments': event['attachments'],
            'created_at': event['created_at']
        }))
    
    # Receive read notification from room group, format it to json and send it to clients
    async def messages_read(self, event):
        # Send read notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'read',
            'reader_id': event['reader_id']
        }))
    


#ACTUAL PROCESS
# "self.channel_layer.group_send" pushes/sends the message (in dictionary format) to the entire room group (where there is all WebSocket clients in that group).
# 'chat_message' method receives that pushed/sent dictionary(from the room group) and converts it to a JSON-encoded string. Then, it sends the JSON message to each WebSocket client using their individual WebSocket connection (via await self.send).
# The dictionary that is sent using group_send is passed to the chat_message method as the event parameter.
# It's the 'chat_message' method that actually uses the user's assigned self.channel_name (WebSocket connection) to send the message to each WebSocket client (using their individual self.channel_name).
# SO, 'group_send' handles the distribution of the message to the group, and chat_message is responsible for formatting and sending the message to the clients over their WebSocket connections.






                                                            #Asynchronous DATABASE CALLS



    @database_sync_to_async
    def user_in_conversation(self, user_id, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            return conversation.participants.filter(id=user_id).exists()
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, conversation_id, sender_id, content, attachments):
        message = Message.objects.create(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            attachments=attachments
        )
        return {
            'id': message.id,
            'created_at': message.created_at.isoformat()
        }
    
    @database_sync_to_async
    def get_conversation_messages(self, conversation_id):
        messages = Message.objects.filter(conversation_id=conversation_id).order_by('created_at')
        return [
            {
                'id': message.id,
                'content': message.content,
                'sender_id': message.sender_id,
                'sender_name': message.sender.username,
                'attachments': message.attachments,
                'is_read': message.is_read,
                'created_at': message.created_at.isoformat()
            }
            for message in messages
        ]
    
    @database_sync_to_async
    def mark_messages_as_read(self, conversation_id, user_id):
        Message.objects.filter(
            conversation_id=conversation_id,
            is_read=False
        ).exclude(
            sender_id=user_id
        ).update(is_read=True)

    #In the database, only the messages that weren't sent by the current user will be marked as read. This is because the logic excludes the user's own sent messages from being marked as read. The server checks which messages in the conversation were sent by others and updates their status to read.
    #so the messages in the given converstaion(conversation_id) in which the sender of those messages is not the current user will be marked as read