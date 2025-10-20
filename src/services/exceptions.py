# src/services/exceptions.py

# --- General Exceptions ---
class VmNotFoundError(Exception):
    """VM을 찾을 수 없을 때"""
    pass

class ProjectNotFoundError(Exception):
    """프로젝트를 찾을 수 없을 때"""
    pass

class UserNotFoundError(Exception):
    """사용자를 찾을 수 없을 때"""
    pass

class RoleNotFoundError(Exception):
    """역할을 찾을 수 없을 때"""
    pass

class ImageNotFoundError(Exception):
    """이미지를 찾을 수 없을 때"""
    pass

# --- Creation/Validation Exceptions ---
class VmAlreadyExistsError(Exception):
    """VM 이름이 이미 존재할 때"""
    pass

class ProjectCreationError(Exception):
    """프로젝트 생성 실패 시"""
    pass

class UserCreationError(Exception):
    """사용자 생성 실패 시"""
    pass

class ProjectNotEmptyError(Exception):
    """비어있지 않은 프로젝트를 삭제하려고 할 때"""
    pass

class VmCreationError(Exception):
    """VM 생성 과정(디스크, libvirt 등)에서 오류 발생 시"""
    pass

# --- Auth Exceptions ---
class TokenInvalidError(Exception):
    """토큰이 유효하지 않거나 없을 때"""
    pass

class AuthenticationError(Exception):
    """사용자 자격 증명 실패 시"""
    pass
