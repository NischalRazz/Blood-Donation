from flask import Blueprint, jsonify, request, render_template, abort, current_app
from flask_login import current_user, login_required
from models import db, ChatSession, Message, User, Notification
from sqlalchemy import or_
from datetime import datetime

chat = Blueprint('chat', __name__, url_prefix='/chat')

@chat.route('/')
@login_required
def chat_list():
    """View list of all chats for the current user"""
    # Get all chat sessions where user is either donor or receiver
    chat_sessions = ChatSession.query.filter(
        or_(
            ChatSession.donor_id == current_user.id,
            ChatSession.receiver_id == current_user.id
        )
    ).order_by(ChatSession.last_message_at.desc()).all()
    
    return render_template('chat/chat_list.html', chat_sessions=chat_sessions, Message=Message)

@chat.route('/<int:user_id>')
@login_required
def chat_view(user_id):
    """View chat with a specific user"""
    other_user = User.query.get_or_404(user_id)
    
    # Don't allow users to chat with themselves
    if user_id == current_user.id:
        abort(400)
    
    # Find existing chat session or create new one
    chat_session = ChatSession.query.filter(
        or_(
            db.and_(
                ChatSession.donor_id == current_user.id,
                ChatSession.receiver_id == other_user.id
            ),
            db.and_(
                ChatSession.donor_id == other_user.id,
                ChatSession.receiver_id == current_user.id
            )
        )
    ).first()
    
    if not chat_session:
        # Create new chat session (determine who is donor/receiver)
        if current_user.role == 'donor':
            donor_id = current_user.id
            receiver_id = other_user.id
        else:
            donor_id = other_user.id
            receiver_id = current_user.id
            
        chat_session = ChatSession(
            donor_id=donor_id,
            receiver_id=receiver_id
        )
        db.session.add(chat_session)
        db.session.commit()
    
    # Mark unread messages as read
    Message.query.filter_by(
        chat_session_id=chat_session.id,
        sender_id=other_user.id,
        is_read=False
    ).update({Message.is_read: True})
    db.session.commit()
    
    return render_template('chat/chat_view.html', 
                         chat_session=chat_session, 
                         other_user=other_user)

def csrf_exempt(view):
    """Mark a view as CSRF exempt"""
    if not hasattr(view, '_csrf_exempt'):
        view._csrf_exempt = True
    return view

@chat.route('/messages/<int:chat_session_id>')
@csrf_exempt
@login_required
def get_messages(chat_session_id):
    """API endpoint to get messages for a chat session"""
    chat_session = ChatSession.query.get_or_404(chat_session_id)
    
    # Check if user is part of this chat
    if current_user.id not in [chat_session.donor_id, chat_session.receiver_id]:
        abort(403)
    
    # Get messages, limited to last 100 for performance
    messages = Message.query.filter_by(chat_session_id=chat_session_id)\
        .order_by(Message.created_at.desc())\
        .limit(100).all()
    
    return jsonify([{
        'id': msg.id,
        'sender_id': msg.sender_id,
        'sender_name': User.query.get(msg.sender_id).get_full_name(),
        'content': msg.content,
        'attachment_url': msg.attachment_url,
        'is_read': msg.is_read,
        'created_at': msg.created_at.isoformat()
    } for msg in messages])

@chat.route('/messages/<int:chat_session_id>/send', methods=['POST'])
@csrf_exempt
@login_required
def send_message(chat_session_id):
    """API endpoint to send a message"""
    chat_session = ChatSession.query.get_or_404(chat_session_id)
    
    # Check if user is part of this chat
    if current_user.id not in [chat_session.donor_id, chat_session.receiver_id]:
        abort(403)
    
    data = request.json
    if not data or 'content' not in data:
        abort(400)
    
    # Create new message
    message = Message(
        chat_session_id=chat_session_id,
        sender_id=current_user.id,
        content=data['content'],
        attachment_url=data.get('attachment_url')
    )
    
    # Update chat session's last message time
    chat_session.last_message_at = datetime.utcnow()
    
    db.session.add(message)
    db.session.commit()
    
    # Create notification for recipient
    recipient_id = chat_session.receiver_id if current_user.id == chat_session.donor_id else chat_session.donor_id
    Notification.create_notification(
        user_id=recipient_id,
        title="New Message",
        message=f"You have a new message from {current_user.get_full_name()}",
        type="info",
        link=f"/chat/{current_user.id}"
    )
    
    return jsonify({
        'id': message.id,
        'sender_id': message.sender_id,
        'sender_name': current_user.get_full_name(),
        'content': message.content,
        'attachment_url': message.attachment_url,
        'is_read': message.is_read,
        'created_at': message.created_at.isoformat()
    })

@chat.route('/messages/<int:message_id>/read', methods=['POST'])
@csrf_exempt
@login_required
def mark_read(message_id):
    """API endpoint to mark a message as read"""
    message = Message.query.get_or_404(message_id)
    chat_session = message.chat_session
    
    # Check if user is the recipient
    if current_user.id not in [chat_session.donor_id, chat_session.receiver_id]:
        abort(403)
    
    if not message.is_read and message.sender_id != current_user.id:
        message.is_read = True
        db.session.commit()
    
    return jsonify({'success': True})

@chat.route('/messages/<int:chat_session_id>/unread')
@csrf_exempt
@login_required
def unread_count(chat_session_id):
    """API endpoint to get number of unread messages"""
    chat_session = ChatSession.query.get_or_404(chat_session_id)
    
    # Check if user is part of this chat
    if current_user.id not in [chat_session.donor_id, chat_session.receiver_id]:
        abort(403)
    
    count = Message.query.filter_by(
        chat_session_id=chat_session_id,
        sender_id=chat_session.donor_id if current_user.id == chat_session.receiver_id else chat_session.receiver_id,
        is_read=False
    ).count()
    
    return jsonify({'unread_count': count})
