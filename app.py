import json
import os
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
from abc import ABC, abstractmethod

# ==========================================
# PAGE CONFIG & STYLING
# ==========================================
st.set_page_config(page_title="Investment Portfolio Manager", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .marquee-container {
        overflow: hidden; white-space: nowrap;
        background: linear-gradient(90deg, #1f4068, #162447);
        color: #ffffff; padding: 10px; font-weight: bold;
        border-radius: 8px; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .marquee-text {
        display: inline-block;
        animation: marquee 18s linear infinite;
    }
    @keyframes marquee {
        0% { transform: translateX(100%); }
        100% { transform: translateX(-100%); }
    }
    </style>
""", unsafe_allow_html=True)

# Sliding Team Banner (DO NOT CHANGE)
st.markdown("""
    <div class="marquee-container">
        <span class="marquee-text">🚀 IOOP Final Project | Group Members: M. Rasub Khan (25K-5620) | Muavia Mustufa Ansari (25K-5682) | Muhammad Hassan (25K-5610) 🚀</span>
    </div>
""", unsafe_allow_html=True)

def speak(text):
    """Browser-based Text-to-Speech voice announcement."""
    clean_text = text.replace('"', '').replace("'", "")
    components.html(f"""
        <script>
            window.speechSynthesis.cancel();
            var msg = new SpeechSynthesisUtterance("{clean_text}");
            msg.rate = 1.0;
            msg.pitch = 1.0;
            window.speechSynthesis.speak(msg);
        </script>
    """, height=0, width=0)

# ==========================================
# EXCEPTIONS & CONVERTER
# ==========================================
class PortfolioError(Exception): pass
class InvalidPriceError(PortfolioError): pass
class InvalidQuantityError(PortfolioError): pass

class CurrencyConverter:
    RATES = {"PKR": 1.0, "USD": 280.0}
    @staticmethod
    def convert(amount, from_curr, to_curr):
        if from_curr == to_curr: return amount
        return (amount * CurrencyConverter.RATES.get(from_curr, 1.0)) / CurrencyConverter.RATES.get(to_curr, 280.0)

class Goal:
    def __init__(self, target=1000000.0, curr="PKR"):
        self.target_amount, self.currency = target, curr
    def calculate_progress(self, total_pkr):
        target_pkr = CurrencyConverter.convert(self.target_amount, self.currency, "PKR")
        return min((total_pkr / target_pkr) * 100.0 if target_pkr > 0 else 0.0, 100.0)
    def to_dict(self): return {"target_amount": self.target_amount, "currency": self.currency}
    @classmethod
    def from_dict(cls, d): return cls(d.get("target_amount", 1000000.0), d.get("currency", "PKR"))

# ==========================================
# ASSET HIERARCHY (OOP)
# ==========================================
class Asset(ABC):
    def __init__(self, name, qty, curr_price, buy_price, curr="PKR"):
        self.name, self.quantity, self._current_price, self.buy_price, self.currency = name, qty, curr_price, buy_price, curr
    @property
    def current_price(self): return self._current_price
    @current_price.setter
    def current_price(self, val):
        if val < 0: raise InvalidPriceError("Price cannot be negative!")
        self._current_price = val
    def total_value(self): return self.quantity * self._current_price
    def profit_loss(self): return self.quantity * (self._current_price - self.buy_price)
    @abstractmethod
    def risk_level(self): pass
    @abstractmethod
    def asset_type(self): pass
    def to_dict(self):
        return {"type": self.asset_type(), "name": self.name, "quantity": self.quantity, "current_price": self._current_price, "buy_price": self.buy_price, "currency": self.currency}

class Stock(Asset):
    def risk_level(self): return "High"
    def asset_type(self): return "Stock"

class Bond(Asset):
    def __init__(self, name, qty, curr_price, buy_price, curr="PKR", rate=5.0):
        super().__init__(name, qty, curr_price, buy_price, curr)
        self.interest_rate = rate
    def risk_level(self): return "Low"
    def asset_type(self): return "Bond"
    def to_dict(self):
        d = super().to_dict()
        d["interest_rate"] = self.interest_rate
        return d

class Coin(Asset):
    def risk_level(self): return "Very High"
    def asset_type(self): return "Coin"

# ==========================================
# LINKED LIST FOR TRANSACTIONS
# ==========================================
class Node:
    def __init__(self, record): self.record, self.next = record, None

class TransactionHistory:
    def __init__(self): self.head = None
    def add_transaction(self, record):
        new_node = Node(record)
        if not self.head: self.head = new_node
        else:
            curr = self.head
            while curr.next: curr = curr.next
            curr.next = new_node
    def get_all(self):
        records, curr = [], self.head
        while curr:
            records.append(curr.record)
            curr = curr.next
        return records
    def load_from_list(self, records):
        self.head = None
        for r in records: self.add_transaction(r)

# ==========================================
# PORTFOLIO MANAGER
# ==========================================
class Portfolio:
    def __init__(self, filename="portfolio.json"):
        self.filename, self.assets, self.lookup, self.history, self.goal = filename, [], {}, TransactionHistory(), Goal()
        self.load_from_file()
    def update_lookup(self):
        self.lookup = {a.name.lower(): a for a in self.assets}
    def buy_asset(self, atype, name, qty, curr_price, buy_price, curr, **kwargs):
        if not name or not name.strip(): raise PortfolioError("Asset name cannot be empty!")
        if qty <= 0: raise InvalidQuantityError("Quantity must be greater than zero!")
        if curr_price < 0 or buy_price < 0: raise InvalidPriceError("Prices cannot be negative!")
        
        key = name.strip().lower()
        if key in self.lookup:
            ex = self.lookup[key]
            tot_qty = ex.quantity + qty
            ex.buy_price = ((ex.quantity * ex.buy_price) + (qty * buy_price)) / tot_qty
            ex.quantity, ex.current_price = tot_qty, curr_price
        else:
            if atype == "Stock": new_a = Stock(name.strip(), qty, curr_price, buy_price, curr)
            elif atype == "Bond": new_a = Bond(name.strip(), qty, curr_price, buy_price, curr, kwargs.get("interest_rate", 5.0))
            elif atype == "Coin": new_a = Coin(name.strip(), qty, curr_price, buy_price, curr)
            else: raise PortfolioError("Invalid asset type.")
            self.assets.append(new_a)
            self.update_lookup()

        self.history.add_transaction({"action": "BUY", "type": atype, "name": name.strip(), "quantity": qty, "price": curr_price, "currency": curr})
        self.save_to_file()

    def sell_asset(self, name, qty):
        if qty <= 0:
            return False, "Quantity to sell must be greater than zero!"
        key = name.strip().lower()
        if key not in self.lookup:
            return False, f"Asset '{name}' not found in portfolio."
        
        a = self.lookup[key]
        
        if qty > a.quantity:
            return False, f"Insufficient Quantity! You are trying to sell {qty} units, but your current holding is only {a.quantity} units."
        
        a.quantity -= qty
        if a.quantity == 0:
            self.assets = [x for x in self.assets if x.name.lower() != key]
            self.update_lookup()

        self.history.add_transaction({"action": "SELL", "type": a.asset_type(), "name": name.strip(), "quantity": qty, "price": a.current_price, "currency": a.currency})
        self.save_to_file()
        return True, "Success"

    def update_price(self, name, new_p):
        if new_p < 0: raise InvalidPriceError("Price cannot be negative!")
        key = name.lower()
        if key not in self.lookup: raise PortfolioError(f"Asset '{name}' not found.")
        self.lookup[key].current_price = new_p
        self.save_to_file()

    def get_total_value_pkr(self):
        return sum(CurrencyConverter.convert(a.total_value(), a.currency, "PKR") for a in self.assets)

    def get_allocation_by_type(self):
        tot = self.get_total_value_pkr()
        if tot == 0: return {}
        t_totals = {}
        for a in self.assets:
            t_totals[a.asset_type()] = t_totals.get(a.asset_type(), 0.0) + CurrencyConverter.convert(a.total_value(), a.currency, "PKR")
        return {t: (v / tot) * 100.0 for t, v in t_totals.items()}

    def rebalance_plan(self, target_mix):
        tot = self.get_total_value_pkr()
        t_totals = {}
        for a in self.assets:
            t_totals[a.asset_type()] = t_totals.get(a.asset_type(), 0.0) + CurrencyConverter.convert(a.total_value(), a.currency, "PKR")
        return {t: (tot * (pct / 100.0)) - t_totals.get(t, 0.0) for t, pct in target_mix.items()}

    def save_to_file(self):
        data = {"assets": [a.to_dict() for a in self.assets], "transactions": self.history.get_all(), "goal": self.goal.to_dict()}
        try:
            with open(self.filename, "w") as f: json.dump(data, f, indent=4)
        except: pass

    def load_from_file(self):
        if not os.path.exists(self.filename): return
        try:
            with open(self.filename, "r") as f:
                d = json.load(f)
                loaded = []
                for item in d.get("assets", []):
                    t, name, qty, cp, bp, curr = item.get("type"), item.get("name"), item.get("quantity"), item.get("current_price"), item.get("buy_price"), item.get("currency", "PKR")
                    if t == "Stock": loaded.append(Stock(name, qty, cp, bp, curr))
                    elif t == "Bond": loaded.append(Bond(name, qty, cp, bp, curr, item.get("interest_rate", 5.0)))
                    elif t in ["Coin", "Cash"]: loaded.append(Coin(name, qty, cp, bp, curr))
                self.assets = loaded
                self.update_lookup()
                self.history.load_from_list(d.get("transactions", []))
                if "goal" in d: self.goal = Goal.from_dict(d["goal"])
        except: pass

    def export_summary(self):
        lines = ["==========================================", "      INVESTMENT PORTFOLIO SUMMARY        ", "==========================================", f"Total Portfolio Value (PKR): {self.get_total_value_pkr():,.2f}\n", "--- HOLDINGS ---"]
        for a in self.assets: lines.append(f"[{a.asset_type()}] {a.name}: Qty={a.quantity}, Price={a.current_price} {a.currency}, Value={a.total_value():,.2f} {a.currency}")
        lines.append("\n--- ALLOCATION ---")
        for t, pct in self.get_allocation_by_type().items(): lines.append(f"{t}: {pct:.2f}%")
        lines.append("\n--- TRANSACTIONS ---")
        for tx in self.history.get_all(): lines.append(f"{tx['action']} | {tx['type']} | {tx['name']} | Qty: {tx['quantity']} | Price: {tx['price']} {tx['currency']}")
        return "\n".join(lines)

# ==========================================
# STREAMLIT UI
# ==========================================
@st.cache_resource
def get_portfolio(): return Portfolio()
portfolio = get_portfolio()

st.title("📈 Investment Portfolio Manager")
display_currency = st.sidebar.selectbox("Display Currency", ["PKR", "USD"])
menu = st.sidebar.radio("Navigation", ["Dashboard & Holdings", "Buy / Sell Assets", "Update Prices", "Rebalance & Goals", "Transaction History", "Export Summary"])

def fmt(v): return f"{CurrencyConverter.convert(v, 'PKR', display_currency):,.2f} {display_currency}"

if menu == "Dashboard & Holdings":
    st.subheader("📊 Portfolio Dashboard")
    tot_pkr = portfolio.get_total_value_pkr()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(tot_pkr))
    c2.metric("Assets Owned", len(portfolio.assets))
    c3.metric("Goal Progress", f"{portfolio.goal.calculate_progress(tot_pkr):.1f}%")
    st.progress(min(portfolio.goal.calculate_progress(tot_pkr) / 100.0, 1.0))
    st.caption(f"Target: {portfolio.goal.target_amount:,.2f} {portfolio.goal.currency} | Target reached: {portfolio.goal.calculate_progress(tot_pkr):.1f}%")

    st.markdown("---")
    if portfolio.assets:
        st.table([{ "Type": a.asset_type(), "Name": a.name, "Qty": a.quantity, "Price": f"{a.current_price} {a.currency}", "Value": fmt(CurrencyConverter.convert(a.total_value(), a.currency, "PKR")), "Profit/Loss": fmt(CurrencyConverter.convert(a.profit_loss(), a.currency, "PKR")), "Risk": a.risk_level() } for a in portfolio.assets])
        
        # --- INTERACTIVE PLOTLY CHARTS ---
        st.markdown("### Interactive Visual Analytics")
        col_chart1, col_chart2 = st.columns(2)

        alloc = portfolio.get_allocation_by_type()
        if alloc:
            fig_pie = px.pie(
                names=list(alloc.keys()),
                values=list(alloc.values()),
                title="Asset Type Allocation (%)",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            col_chart1.plotly_chart(fig_pie, use_container_width=True)

        asset_names = [a.name for a in portfolio.assets]
        asset_vals = [CurrencyConverter.convert(a.total_value(), a.currency, display_currency) for a in portfolio.assets]
        if asset_names:
            fig_bar = px.bar(
                x=asset_names,
                y=asset_vals,
                labels={'x': 'Asset Name', 'y': f'Value ({display_currency})'},
                title=f"Value per Asset ({display_currency})",
                color=asset_names,
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
            col_chart2.plotly_chart(fig_bar, use_container_width=True)

    else: st.info("No assets found. Go to 'Buy / Sell Assets' to add holdings.")

elif menu == "Buy / Sell Assets":
    st.subheader("🛒 Buy or Sell Assets")
    tab_buy, tab_sell = st.tabs(["Buy Asset", "Sell Asset"])

    with tab_buy:
        b_type = st.selectbox("Asset Type", ["Stock", "Bond", "Coin"], key="b_type_select")
        with st.form("buy_form"):
            if b_type == "Coin":
                b_name = st.selectbox("Select Coin Name", ["BTC", "XRP", "BNB", "DOGE", "ETH"])
            else:
                b_name = st.text_input("Asset Name (e.g., Apple Inc, Pakistan 5Y Bond)")

            b_qty = st.number_input("Quantity", min_value=0.01, value=1.0)
            b_curr_p = st.number_input("Current Price", min_value=0.0, value=100.0)
            b_buy_p = st.number_input("Buy Price (Historical)", min_value=0.0, value=90.0)
            b_curr = st.selectbox("Currency", ["PKR", "USD"])
            rate = st.number_input("Yearly Interest Rate (%)", min_value=0.0, value=10.0) if b_type == "Bond" else 5.0

            if st.form_submit_button("Confirm Buy"):
                try:
                    portfolio.buy_asset(b_type, b_name, b_qty, b_curr_p, b_buy_p, b_curr, interest_rate=rate)
                    msg = f"Successfully bought {b_qty} units of {b_name}"
                    st.success(f"✅ {msg}!")
                    speak(f"You have purchased {b_qty} units of {b_name}")
                except PortfolioError as e: st.error(f"Error: {e}")

    with tab_sell:
        if portfolio.assets:
            s_name = st.selectbox("Select Asset to Sell", [a.name for a in portfolio.assets], key="sell_name_select")
        else:
            s_name = st.text_input("Asset Name to Sell", key="sell_name_input")

        s_qty = st.number_input("Quantity to Sell", min_value=0.01, value=1.0, key="sell_qty_input")
        
        if st.button("Confirm Sell", key="confirm_sell_btn"):
            success, message = portfolio.sell_asset(s_name, s_qty)
            if success:
                msg = f"Successfully sold {s_qty} units of {s_name}"
                st.success(f"✅ {msg}!")
                speak(f"You have sold {s_qty} units of {s_name}")
            else:
                st.warning(f"⚠️ {message}")

elif menu == "Update Prices":
    st.subheader("🔄 Update Asset Price")
    if portfolio.assets:
        with st.form("price_form"):
            sel_a = st.selectbox("Select Asset", [a.name for a in portfolio.assets])
            new_p = st.number_input("New Current Price", min_value=0.0, value=100.0)
            if st.form_submit_button("Update Price"):
                try:
                    portfolio.update_price(sel_a, new_p)
                    st.success(f"✨ Price for {sel_a} updated to {new_p}!")
                except PortfolioError as e: st.error(f"Error: {e}")
    else: st.info("No assets to update.")

elif menu == "Rebalance & Goals":
    st.subheader("⚖️ Rebalance & Goals")
    c1, c2, c3 = st.columns(3)
    ts, tb, tc = c1.number_input("Stock Target %", 0.0, 100.0, 40.0), c2.number_input("Bond Target %", 0.0, 100.0, 30.0), c3.number_input("Coin Target %", 0.0, 100.0, 30.0)
    if st.button("Calculate Rebalance"):
        if ts + tb + tc != 100.0: st.warning("Target percentages must sum up to 100%!")
        else:
            for at, diff in portfolio.rebalance_plan({"Stock": ts, "Bond": tb, "Coin": tc}).items():
                act = "BUY" if diff > 0 else "SELL"
                st.write(f"- **{at}**: Need to **{act}** approx **{fmt(abs(diff))}**")

    st.markdown("---")
    with st.form("goal_form"):
        g_amt, g_c = st.number_input("Target Amount", min_value=1.0, value=portfolio.goal.target_amount), st.selectbox("Goal Currency", ["PKR", "USD"])
        if st.form_submit_button("Save Goal"):
            portfolio.goal = Goal(g_amt, g_c)
            portfolio.save_to_file()
            st.success("🎯 Financial goal updated successfully!")

elif menu == "Transaction History":
    st.subheader("📜 Ordered Transaction History")
    txs = portfolio.history.get_all()
    if txs:
        for idx, tx in enumerate(reversed(txs), 1):
            st.markdown(f"**{idx}.** `[{tx['action']}]` Type: **{tx['type']}** | Name: **{tx['name']}** | Qty: `{tx['quantity']}` | Price: `{tx['price']} {tx['currency']}`")
    else: st.info("No transactions recorded yet.")

elif menu == "Export Summary":
    st.subheader("📥 Export Summary Report")
    summary = portfolio.export_summary()
    st.text_area("Report Preview", summary, height=300)
    st.download_button("Download Summary Text File", data=summary, file_name="portfolio_summary.txt", mime="text/plain")