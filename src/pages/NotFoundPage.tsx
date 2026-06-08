import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center">
        <p className="font-mono text-8xl font-bold text-border-visible">404</p>
        <h2 className="mt-6 font-serif text-2xl font-bold">页面不存在</h2>
        <p className="mt-2 text-sm leading-6 text-text-secondary">
          这个地址没有对应的 StructForge 页面。
        </p>
        <div className="mt-8">
          <Link to="/projects">
            <Button variant="primary">返回项目列表</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
