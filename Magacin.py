from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return "Aplikacija radi! Idi na /admin za pretragu."

@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

if __name__ == '__main__':
    app.run(debug=True)
