import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ErrorAlert } from '../components/ui/ErrorAlert';

export default function NotFoundPage() {
  return (
    <div className="mx-auto max-w-xl">
      <ErrorAlert
        title={'\u9875\u9762\u4e0d\u5b58\u5728'}
        description={'\u8fd9\u4e2a\u5730\u5740\u6ca1\u6709\u5bf9\u5e94\u7684 StructForge \u9875\u9762\u3002'}
        action={
          <Link to="/projects">
            <Button>{'\u8fd4\u56de\u9879\u76ee\u5217\u8868'}</Button>
          </Link>
        }
      />
    </div>
  );
}
