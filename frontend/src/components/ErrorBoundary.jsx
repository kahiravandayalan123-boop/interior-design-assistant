import { Component } from "react";

// Catches render-time crashes anywhere below it so the user sees a plain
// "something broke, start over" card instead of a blank white screen.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled UI error:", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="wrap">
        <div className="card">
          <h2>Something went wrong</h2>
          <p className="card-sub">
            The app hit an unexpected error and couldn't continue. Your session data
            wasn't lost on the server — reloading will get you back to a clean screen.
          </p>
          <div className="actions">
            <button className="primary" onClick={() => window.location.reload()}>
              Reload the app
            </button>
          </div>
        </div>
      </div>
    );
  }
}
