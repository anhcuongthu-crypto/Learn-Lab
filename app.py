import os
from datetime import date, datetime, timedelta
import secrets, smtplib, ssl, json, urllib.parse, urllib.request
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import selectinload
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
app=Flask(__name__); app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","change-me")
url=os.getenv("DATABASE_URL","sqlite:///learnlab.db")
if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_DATABASE_URI"]=url
if url.startswith("postgresql://"): app.config["SQLALCHEMY_ENGINE_OPTIONS"]={"pool_pre_ping":True,"pool_recycle":300}
db=SQLAlchemy(app); lm=LoginManager(app); lm.login_view="login"
class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(50),unique=True); email=db.Column(db.String(120),unique=True); password=db.Column(db.String(255)); xp=db.Column(db.Integer,default=0); hearts=db.Column(db.Integer,default=5); streak=db.Column(db.Integer,default=0); last_study=db.Column(db.Date); admin=db.Column(db.Boolean,default=False)
class Course(db.Model):
 id=db.Column(db.Integer,primary_key=True); title=db.Column(db.String(120)); description=db.Column(db.String(300)); emoji=db.Column(db.String(12),default="📘"); lessons=db.relationship("Lesson",backref="course",cascade="all,delete-orphan",lazy="selectin")
class Lesson(db.Model):
 id=db.Column(db.Integer,primary_key=True); course_id=db.Column(db.Integer,db.ForeignKey("course.id")); title=db.Column(db.String(120)); description=db.Column(db.String(250)); questions=db.relationship("Question",backref="lesson",cascade="all,delete-orphan",lazy="selectin")
class Question(db.Model):
 id=db.Column(db.Integer,primary_key=True); lesson_id=db.Column(db.Integer,db.ForeignKey("lesson.id")); prompt=db.Column(db.String(500)); answer=db.Column(db.String(250)); choices=db.Column(db.String(600),default=""); hint=db.Column(db.String(250),default="")
class Progress(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); lesson_id=db.Column(db.Integer,db.ForeignKey("lesson.id")); score=db.Column(db.Integer,default=0)
 __table_args__=(db.UniqueConstraint("user_id","lesson_id"),)
class Attempt(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),index=True); lesson_id=db.Column(db.Integer,db.ForeignKey("lesson.id"),index=True)
 score=db.Column(db.Integer,default=0); total=db.Column(db.Integer,default=0); percent=db.Column(db.Integer,default=0)
 started_at=db.Column(db.DateTime,default=datetime.utcnow); completed_at=db.Column(db.DateTime)
 answers=db.relationship("AttemptAnswer",backref="attempt",cascade="all,delete-orphan",lazy="selectin",order_by="AttemptAnswer.id")
class AttemptAnswer(db.Model):
 id=db.Column(db.Integer,primary_key=True); attempt_id=db.Column(db.Integer,db.ForeignKey("attempt.id"),index=True)
 question_id=db.Column(db.Integer,db.ForeignKey("question.id"),nullable=True); question_text=db.Column(db.String(500)); answer_text=db.Column(db.String(1000))
 correct_answer=db.Column(db.String(250)); is_correct=db.Column(db.Boolean,default=False); answered_at=db.Column(db.DateTime,default=datetime.utcnow)
@lm.user_loader
def load(uid): return db.session.get(User,int(uid))
def seed():
 if Course.query.first(): return
 c=Course(title="Tiếng Anh cơ bản",description="Từ vựng và giao tiếp mỗi ngày.",emoji="🌎"); db.session.add(c); db.session.flush()
 l=Lesson(course_id=c.id,title="Xin chào!",description="Lời chào cơ bản"); db.session.add(l); db.session.flush()
 db.session.add_all([Question(lesson_id=l.id,prompt="Xin chào trong tiếng Anh?",answer="Hello",choices="Hello|Goodbye|Thanks|Sorry",hint="Bắt đầu bằng H"),Question(lesson_id=l.id,prompt="Cảm ơn trong tiếng Anh?",answer="Thank you",choices="Please|Thank you|Sorry|Hi"),Question(lesson_id=l.id,prompt="Chọn câu giới thiệu tên đúng.",answer="My name is Lan.",choices="I name Lan.|My name is Lan.|Me Lan.|My names Lan.")]); db.session.commit()
@app.route("/")
def home(): return redirect(url_for("dashboard")) if current_user.is_authenticated else render_template("home.html")
@app.route("/register",methods=["GET","POST"])
def register():
 if request.method=="POST":
  name=request.form["username"].strip(); email=request.form["email"].lower().strip(); pw=request.form["password"]
  if len(name)<2 or len(pw)<6: flash("Tên tài khoản cần ít nhất 2 ký tự, mật khẩu ít nhất 6 ký tự.")
  elif User.query.filter((User.username==name)|(User.email==email)).first(): flash("Tên hoặc email đã tồn tại.")
  else:
   u=User(username=name,email=email,password=generate_password_hash(pw),admin=email==os.getenv("ADMIN_EMAIL","").strip().lower())
   db.session.add(u); db.session.commit(); login_user(u); return redirect(url_for("dashboard"))
 return render_template("auth.html",register=True)
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  identity=request.form["identity"].strip()
  u=User.query.filter((User.email==identity.lower())|(User.username==identity)).first()
  if u and check_password_hash(u.password,request.form["password"]):
   admin_email=os.getenv("ADMIN_EMAIL","").strip().lower()
   if admin_email and u.email.lower()==admin_email and not u.admin: u.admin=True; db.session.commit()
   login_user(u); return redirect(url_for("dashboard"))
  else: flash("Sai thông tin đăng nhập.")
 return render_template("auth.html",register=False)
@app.route("/google-login")
def google_login():
 client=os.getenv("GOOGLE_CLIENT_ID","").strip()
 if not client: flash("Đăng nhập Google chưa được cấu hình GOOGLE_CLIENT_ID trên Render."); return redirect(url_for("login"))
 state=secrets.token_urlsafe(24); session["google_state"]=state
 params={"client_id":client,"redirect_uri":url_for("google_callback",_external=True),"response_type":"code","scope":"openid email profile","state":state,"prompt":"select_account"}
 return redirect("https://accounts.google.com/o/oauth2/v2/auth?"+urllib.parse.urlencode(params))
@app.route("/google-callback")
def google_callback():
 if request.args.get("state")!=session.pop("google_state",None) or not request.args.get("code"): flash("Xác thực Google không hợp lệ."); return redirect(url_for("login"))
 client=os.getenv("GOOGLE_CLIENT_ID","").strip(); secret=os.getenv("GOOGLE_CLIENT_SECRET","").strip()
 if not client or not secret: flash("Thiếu cấu hình Google OAuth."); return redirect(url_for("login"))
 try:
  token_data=urllib.parse.urlencode({"code":request.args["code"],"client_id":client,"client_secret":secret,"redirect_uri":url_for("google_callback",_external=True),"grant_type":"authorization_code"}).encode()
  req=urllib.request.Request("https://oauth2.googleapis.com/token",data=token_data,headers={"Content-Type":"application/x-www-form-urlencoded"})
  token=json.loads(urllib.request.urlopen(req,timeout=15).read().decode())
  req=urllib.request.Request("https://openidconnect.googleapis.com/v1/userinfo",headers={"Authorization":"Bearer "+token["access_token"]})
  info=json.loads(urllib.request.urlopen(req,timeout=15).read().decode())
  email=info.get("email","").lower()
  if not email or not info.get("email_verified"): raise ValueError("Google chưa xác minh email.")
  u=User.query.filter_by(email=email).first()
  if not u:
   base=(info.get("given_name") or email.split("@")[0])[:40]; username=base; n=1
   while User.query.filter_by(username=username).first(): username=f"{base[:44]}{n}"; n+=1
   u=User(username=username,email=email,password=generate_password_hash(secrets.token_urlsafe(32)),admin=email==os.getenv("ADMIN_EMAIL","").strip().lower())
   db.session.add(u); db.session.commit()
  elif email==os.getenv("ADMIN_EMAIL","").strip().lower() and not u.admin: u.admin=True; db.session.commit()
  login_user(u); return redirect(url_for("dashboard"))
 except Exception as e: flash("Đăng nhập Google thất bại: "+str(e))
 return redirect(url_for("login"))
@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("home"))
@app.route("/dashboard")
@login_required
def dashboard(): return render_template("dashboard.html",courses=Course.query.options(selectinload(Course.lessons)).all(),leaders=User.query.order_by(User.xp.desc()).limit(5).all())
@app.route("/course/<int:cid>")
@login_required
def course(cid): return render_template("course.html",course=Course.query.options(selectinload(Course.lessons)).filter_by(id=cid).first_or_404())
@app.route("/lesson/<int:lid>",methods=["GET"])
@login_required
def lesson(lid):
 l=Lesson.query.options(selectinload(Lesson.questions)).filter_by(id=lid).first_or_404()
 if not l.questions: flash("Bài học chưa có câu hỏi."); return redirect(url_for("course",cid=l.course_id))
 attempt=Attempt(user_id=current_user.id,lesson_id=lid,total=len(l.questions))
 db.session.add(attempt); db.session.commit()
 session["lesson_run"]={"lesson_id":lid,"attempt_id":attempt.id,"index":0,"score":0,"finished":False}
 return render_template("lesson.html",lesson=l)
@app.route("/lesson/<int:lid>/answer",methods=["POST"])
@login_required
def lesson_answer(lid):
 run=session.get("lesson_run")
 if not run or run.get("lesson_id")!=lid or run.get("finished"):
  return jsonify({"error":"Phiên học không hợp lệ. Hãy tải lại bài học."}),400
 l=Lesson.query.options(selectinload(Lesson.questions)).filter_by(id=lid).first_or_404(); qs=l.questions
 idx=run["index"]
 if idx>=len(qs): return jsonify({"error":"Bài học đã kết thúc."}),400
 attempt=Attempt.query.filter_by(id=run.get("attempt_id"),user_id=current_user.id,lesson_id=lid,completed_at=None).first()
 if not attempt: return jsonify({"error":"Không tìm thấy lượt làm bài. Hãy tải lại bài học."}),400
 q=qs[idx]; data=request.get_json(silent=True) or {}
 answer=str(data.get("answer","")).strip()
 if not answer: return jsonify({"error":"Hãy chọn hoặc nhập câu trả lời."}),400
 correct=answer.casefold()==q.answer.strip().casefold()
 db.session.add(AttemptAnswer(attempt_id=attempt.id,question_id=q.id,question_text=q.prompt,answer_text=answer,correct_answer=q.answer,is_correct=correct))
 if correct: run["score"]+=1
 run["index"]+=1
 done=run["index"]>=len(qs)
 pct=round(run["score"]*100/len(qs)) if qs else 0
 attempt.score=run["score"]; attempt.percent=pct
 if done:
  run["finished"]=True; attempt.completed_at=datetime.utcnow()
  p=Progress.query.filter_by(user_id=current_user.id,lesson_id=lid).first()
  if not p: p=Progress(user_id=current_user.id,lesson_id=lid); db.session.add(p)
  p.score=max(int(p.score or 0),pct)
  if pct>=60:
   current_user.xp+=run["score"]*10+10
   if current_user.last_study!=date.today(): current_user.streak=current_user.streak+1 if current_user.last_study and (date.today()-current_user.last_study).days==1 else 1; current_user.last_study=date.today()
  else: current_user.hearts=max(0,current_user.hearts-1)
 db.session.commit()
 session["lesson_run"]=run
 return jsonify({"correct":correct,"correct_answer":q.answer,"progress":run["score"],"total":len(qs),"next_index":run["index"],"done":done,"score":run["score"],"pct":pct,"result_url":url_for("lesson_result",lid=lid) if done else None})
@app.route("/lesson/<int:lid>/result")
@login_required
def lesson_result(lid):
 l=Lesson.query.options(selectinload(Lesson.questions)).filter_by(id=lid).first_or_404(); run=session.get("lesson_run")
 if not run or run.get("lesson_id")!=lid or not run.get("finished"): return redirect(url_for("lesson",lid=lid))
 total=len(l.questions)
 return render_template("result.html",lesson=l,score=run["score"],total=total,pct=round(run["score"]*100/total) if total else 0)
@app.route("/leaderboard")
@login_required
def leaderboard(): return render_template("leaderboard.html",users=User.query.order_by(User.xp.desc()).limit(100).all())
@app.route("/admin",methods=["GET","POST"])
@login_required
def admin():
 if not current_user.admin: return redirect(url_for("dashboard"))
 if request.method=="POST":
  kind=request.form["kind"]
  if kind=="course": db.session.add(Course(title=request.form["title"],description=request.form.get("description",""),emoji=request.form.get("emoji","📘")))
  elif kind=="lesson": db.session.add(Lesson(course_id=int(request.form["course_id"]),title=request.form["title"],description=request.form.get("description","")))
  elif kind=="question": db.session.add(Question(lesson_id=int(request.form["lesson_id"]),prompt=request.form["prompt"],answer=request.form["answer"],choices=request.form.get("choices",""),hint=request.form.get("hint","")))
  db.session.commit(); flash("Đã lưu nội dung.")
 return render_template("admin.html",courses=Course.query.all())
@app.route("/health")
def health(): return {"status":"ok","app":"LearnLab"}
with app.app_context(): db.create_all(); seed()
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
