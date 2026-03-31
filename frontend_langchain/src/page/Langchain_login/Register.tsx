import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Card, Form, Input, Alert, Spin, Typography } from 'antd';
import { register } from '../../services/api';
import { UserDto, FormErrors } from './types';
import { SM2Utils } from '../../utils/sm2';

const { Title } = Typography;

type RegisterViewProps = {
  formData: UserDto;
  errors: FormErrors;
  loading: boolean;
  successMessage: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSubmit: (e: React.FormEvent) => void;
};

const RegisterView: React.FC<RegisterViewProps> = ({
  formData,
  errors,
  loading,
  successMessage,
  onChange,
  onSubmit,
}) => {
  return (
    <div className="auth-page">
      <Card className="auth-card" variant="outlined">
        <Title level={2} className="auth-title">用户注册</Title>

        {successMessage && (
          <Alert
            type="success"
            showIcon
            message={successMessage}
            style={{ marginBottom: 16 }}
          />
        )}

        {errors.submit && (
          <Alert
            type="error"
            showIcon
            message={errors.submit}
            style={{ marginBottom: 16 }}
          />
        )}

        <Form layout="vertical" onSubmitCapture={onSubmit}>
          <Form.Item
            label="用户名"
            validateStatus={errors.name ? 'error' : ''}
            help={errors.name}
          >
            <Input size="large" type="text" id="name" name="name" value={formData.name}
              onChange={onChange}
              placeholder="请输入用户名"
            />
          </Form.Item>

          <Form.Item
            label="邮箱"
            validateStatus={errors.email ? 'error' : ''}
            help={errors.email}
          >
            <Input size="large" type="email" id="email" name="email" value={formData.email}
              onChange={onChange}
              placeholder="请输入邮箱"
            />
          </Form.Item>

          <Form.Item
            label="密码"
            validateStatus={errors.password ? 'error' : ''}
            help={errors.password}
          >
            <Input.Password size="large" id="password" name="password" value={formData.password}
              onChange={onChange}
              placeholder="请输入密码"
            />
          </Form.Item>

          <Button type="primary" htmlType="submit" className="auth-submit" size="large" block disabled={loading}>
            {loading ? <Spin size="small" /> : '注册'}
          </Button>
        </Form>

        <p className="auth-link-text">
          已有账号？ <Link to="/login">去登录</Link>
        </p>
      </Card>
    </div>
  );
};

const Register: React.FC = () => {
  const navigate = useNavigate();

  // 表单状态
  const [formData, setFormData] = useState<UserDto>({
    name: '',
    password: '',
    email: '',
  });

  // 错误信息
  const [errors, setErrors] = useState<FormErrors>({});

  // 加载状态
  const [loading, setLoading] = useState(false);

  // 成功信息
  const [successMessage, setSuccessMessage] = useState<string>('');

  // 处理表单输入变化
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));

    // 清除对应字段的错误信息
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];

        // 邮箱修改时，同步清除顶部“已被注册”提示
        if (name === 'email' && newErrors.submit?.includes('已被注册')) {
          delete newErrors.submit;
        }

        return newErrors;
      });
    }
  };

  // 表单验证
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = '用户名不能为空';
    }

    if (!formData.email.trim()) {
      newErrors.email = '邮箱不能为空';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = '请输入有效的邮箱地址';
    }

    if (!formData.password) {
      newErrors.password = '密码不能为空';
    } else if (formData.password.length < 6) {
      newErrors.password = '密码长度不能少于6位';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // 处理表单提交
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // 验证表单
    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setSuccessMessage('');

    try {
      console.log('开始注册，原始表单数据:', formData);
      // 加密密码
      const encryptedPassword = SM2Utils.encrypt(formData.password);
      console.log('加密后的密码:', encryptedPassword);
      
      const encryptedFormData = {
        ...formData,
        password: encryptedPassword
      };
      console.log('加密后的表单数据:', encryptedFormData);
      
      console.log('准备发送注册请求...');
      const response = await register(encryptedFormData);
      console.log('注册请求响应:', response);

      if (response.success) {
        setSuccessMessage('注册成功！');
        // 3秒后跳转到登录页面
        setTimeout(() => {
          navigate('/login');
        }, 3000);
      } else {
        const errorMessage = response?.message || response?.msg || '注册失败，请稍后重试';

        // 已注册邮箱优先展示在邮箱输入框下
        if (errorMessage.includes('邮箱') && errorMessage.includes('已被注册')) {
          setErrors({ email: errorMessage, submit: errorMessage });
        } else {
          setErrors({ submit: errorMessage });
        }
      }
    } catch (error: any) {
      console.error('注册失败，错误信息:', error);
      const errorMessage = error?.response?.data?.message || error?.response?.data?.msg || '注册失败，请稍后重试';
      setErrors({ submit: errorMessage });
    } finally {
      setLoading(false);
    }
  };

  return (
    <RegisterView
      formData={formData}
      errors={errors}
      loading={loading}
      successMessage={successMessage}
      onChange={handleChange}
      onSubmit={handleSubmit}
    />
  );
};

export default Register;
