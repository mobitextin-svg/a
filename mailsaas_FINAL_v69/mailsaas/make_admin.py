"""
Make an account an admin (or list accounts).

Usage (from inside the `mailsaas` folder):

    python make_admin.py                      # list all accounts + who is admin
    python make_admin.py you@example.com      # promote that account to Admin

This flips the account's admin flag and the user's role, so logging in with that
email shows the Admin panel.
"""
import os
import sys
import sqlite3

DB = os.environ.get(
    "MAILSAAS_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "mailsaas.sqlite3"))


def main():
    if not os.path.exists(DB):
        print(f"No database found at {DB}\nStart the app once (create an account), "
              "then run this again.")
        return
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "SELECT u.email, u.name, u.role, a.id acct, a.is_admin, a.name company"
        " FROM users u JOIN accounts a ON a.id = u.account_id ORDER BY a.id").fetchall()

    if len(sys.argv) < 2:
        print("\n  Accounts on this platform:\n  " + "-" * 50)
        for r in rows:
            tag = "  <-- ADMIN" if r["is_admin"] else ""
            print(f"  #{r['acct']:>2}  {r['email']:<28} role={r['role']:<11}{tag}")
        print("\n  To make one an admin:  python make_admin.py <email>\n")
        con.close()
        return

    email = sys.argv[1].strip().lower()
    u = con.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
    if not u:
        print(f"No user found with email '{email}'.")
        print("Run with no arguments to list accounts.")
        con.close()
        return

    con.execute("UPDATE accounts SET is_admin=1 WHERE id=?", (u["account_id"],))
    con.execute("UPDATE users SET role='Super Admin', status='active' WHERE id=?",
                (u["id"],))
    con.commit()
    con.close()
    print(f"\n  ✅ {email} is now an ADMIN (Super Admin).")
    print("  Log in with this account to see the Admin panel.\n")


if __name__ == "__main__":
    main()
