import os
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
app=Flask(__name__); app.config["SECRET_KEY"]=os.getenv("SECRET_KEY","change-me")
url=os.getenv("DATABASE_URL","sqlite:///learnlab.db")
if url.startswith("postgres://"): url=url.replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_DATABASE_URI"]=url; db=SQLAlchemy(app); lm=LoginManager(app); lm.login_view="login"
class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(50),unique=True); email=db.Column(db.String(120),unique=True); password=db.Column(db.String(255)); xp=db.Column(db.Integer,default=0); hearts=db.Column(db.Integer,default=5); streak=db.Column(db.Integer,default=0); last_study=db.Column(db.Date); admin=db.Column(db.Boolean,default=False)
class Course(db.Model):
 id=db.Column(db.Integer,primary_key=True); title=db.Column(db.String(120)); description=db.Column(db.String(300)); emoji=db.Column(db.String(12),default="📘"); lessons=db.relationship("Lesson",backref="course",cascade="all,delete-orphan")
class Lesson(db.Model):
 id=db.Column(db.Integer,primary_key=True); course_id=db.Column(db.Integer,db.ForeignKey("course.id")); title=db.Column(db.String(120)); description=db.Column(db.String(250)); questions=db.relationship("Question",backref="lesson",cascade="all,delete-orphan")
class Question(db.Model):
 id=db.Column(db.Integer,primary_key=True); lesson_id=db.Column(db.Integer,db.ForeignKey("lesson.id")); prompt=db.Column(db.String(500)); answer=db.Column(db.String(250)); choices=db.Column(db.String(600),default=""); hint=db.Column(db.String(250),default="")
class Progress(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id")); lesson_id=db.Column(db.Integer,db.ForeignKey("lesson.id")); score=db.Column(db.Integer,default=0)
 __table_args__=(db.UniqueConstraint("user_id","lesson_id"),)
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
  if User.query.filter((User.username==name)|(User.email==email)).first(): flash("Tên hoặc email đã tồn tại.")
  else:
   u=User(username=name,email=email,password=generate_password_hash(pw),admin=email==os.getenv("ADMIN_EMAIL","").lower()); db.session.add(u); db.session.commit(); login_user(u); return redirect(url_for("dashboard"))
 return render_template("auth.html",register=True)
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  u=User.query.filter((User.email==request.form["identity"].lower())|(User.username==request.form["identity"])).first()
  if u and check_password_hash(u.password,request.form["password"]): login_user(u); return redirect(url_for("dashboard"))
  flash("Sai thông tin đăng nhập.")
 return render_template("auth.html",register=False)
@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("home"))
@app.route("/dashboard")
@login_required
def dashboard(): return render_template("dashboard.html",courses=Course.query.all(),leaders=User.query.order_by(User.xp.desc()).limit(5).all())
@app.route("/course/<int:cid>")
@login_required
def course(cid): return render_template("course.html",course=Course.query.get_or_404(cid))
@app.route("/lesson/<int:lid>",methods=["GET","POST"])
@login_required
def lesson(lid):
 l=Lesson.query.get_or_404(lid)
 if request.method=="POST":
  qs=l.questions; score=sum(1 for q in qs if request.form.get(str(q.id),"").strip().casefold()==q.answer.strip().casefold()); pct=round(score*100/len(qs)) if qs else 0
  p=Progress.query.filter_by(user_id=current_user.id,lesson_id=lid).first()
  if not p: p=Progress(user_id=current_user.id,lesson_id=lid); db.session.add(p)
  p.score=max(p.score,pct)
  if pct>=60:
   current_user.xp+=score*10+10
   if current_user.last_study!=date.today(): current_user.streak=current_user.streak+1 if current_user.last_study and (date.today()-current_user.last_study).days==1 else 1; current_user.last_study=date.today()
  else: current_user.hearts=max(0,current_user.hearts-1)
  db.session.commit(); return render_template("result.html",lesson=l,score=score,total=len(qs),pct=pct)
 return render_template("lesson.html",lesson=l)
@app.route("/leaderboard")
@login_required
def leaderboard(): return render_template("leaderboard.html",users=User.query.order_by(User.xp.desc()).all())
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
