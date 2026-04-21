export default function InsightBox({ type = 'insight', children }) {
  const cls = type === 'good' ? 'good-box' : type === 'bad' ? 'bad-box' : 'insight-box';
  return <div className={cls}>{children}</div>;
}
