import jsonpickle
from flask import Flask, render_template, jsonify, request, session
from flask_session import Session
from redis import Redis
from teacher import Teacher
from utils import execute_code
import uuid

app = Flask(__name__, static_folder='static', template_folder='templates')

# 配置会话类型为Redis
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = Redis(host='localhost', port=6379)
app.config['SECRET_KEY'] = 'your_secret_key'
Session(app)

@app.before_request
def before_request():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    if 'teacher' not in session:
        session['teacher'] = jsonpickle.encode(Teacher(config_path="config.json", teacher_id=session['session_id']))

@app.route('/clear_session', methods=['POST'])
def clear_session():
    session.clear()
    print('session cleared')
    return '', 204

@app.route('/')
def index():
    teacher = jsonpickle.decode(session['teacher'])
    teacher.clear_all_states()
    teacher.clear_chat_history()
    session['teacher'] = jsonpickle.encode(teacher)
    return render_template('testindex.html')

@app.route('/next_question', methods=['POST'])
def next_question():
    teacher = jsonpickle.decode(session['teacher'])
    teacher.clear_all_states()
    difficulty = request.form['difficulty']
    success = teacher.gen_question(difficulty)
    if success:
        problem_description = teacher.question
        user_code = teacher.user_answer
    else:
        problem_description = "题目生成失败，请重试"
        user_code = "用户代码生成失败，请重试"
    session['teacher'] = jsonpickle.encode(teacher)
    return jsonify({'problem_description': problem_description, 'user_code': user_code})

@app.route('/run_code', methods=['POST'])
def run_code():
    code = request.form['code']
    result = execute_code(code)
    return jsonify({'run_result': result})

@app.route('/check_answer', methods=['POST'])
def check_answer():
    teacher = jsonpickle.decode(session['teacher'])
    user_answer = request.form['answer']
    if user_answer != teacher.user_answer or teacher.explanation == "":
        teacher.check_answer(user_answer)
    is_correct = teacher.is_correct
    answer_analysis = teacher.explanation
    has_question = teacher.question != ""
    session['teacher'] = jsonpickle.encode(teacher)
    return jsonify({'is_correct': is_correct, 'answer_analysis': answer_analysis, 'has_question': has_question})

@app.route('/send_chat', methods=['POST'])
def send_chat():
    teacher = jsonpickle.decode(session['teacher'])
    user_answer = request.form['user_answer']
    user_input = request.form['user_input']
    if len(user_input) > 0:
        response = teacher.chat(user_answer, user_input)
    else:
        response = ""
    session['teacher'] = jsonpickle.encode(teacher)
    return jsonify({'response': response})

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    teacher = jsonpickle.decode(session['teacher'])
    teacher.clear_chat_history()
    session['teacher'] = jsonpickle.encode(teacher)
    return jsonify({'response': "聊天记录已清空"})

if __name__ == '__main__':
    # app.run(debug=False, host='0.0.0.0', port=5000)
    pass
